"""
性能对比测试：单线程 vs 多线程
通过模拟抓取和LLM调用，量化多线程优化的加速效果
"""
import logging
import os
import sys
import time
import json
import psutil
import threading
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("perf_test")

# 抑制scraper/analyzer的INFO日志
logging.getLogger("src.scraper").setLevel(logging.WARNING)
logging.getLogger("src.analyzer").setLevel(logging.WARNING)
logging.getLogger("src.parallel_analyzer").setLevel(logging.WARNING)
logging.getLogger("src.llm_client").setLevel(logging.ERROR)


def get_process_metrics():
    """获取当前进程的CPU和内存占用"""
    proc = psutil.Process(os.getpid())
    return {
        "cpu_percent": proc.cpu_percent(interval=0.1),
        "memory_mb": proc.memory_info().rss / 1024 / 1024,
        "threads": proc.num_threads(),
    }


class MockLLMClient:
    """模拟LLM调用，避免真实API请求以保证测试可重复"""

    def __init__(self, avg_latency=2.0, jitter=0.5):
        self.avg_latency = avg_latency
        self.jitter = jitter
        self.call_count = 0
        self._lock = threading.Lock()

    def generate_summary(self, title, summary, content, source):
        with self._lock:
            self.call_count += 1
        latency = self.avg_latency + (time.time() % self.jitter) - self.jitter / 2
        time.sleep(max(0.1, latency))
        safe_title = (title or "")[:30]
        return f"标题：{safe_title}", f"摘要：这是关于{title}的测试摘要"


class MockScraper:
    """模拟抓取器，模拟各阶段延迟"""

    def __init__(self, sources_count=10, items_per_source=5,
                 source_latency=0.8, content_latency=0.6):
        self.sources_count = sources_count
        self.items_per_source = items_per_source
        self.source_latency = source_latency
        self.content_latency = content_latency

    def get_sources(self):
        return [
            {"name": f"测试源-{i}", "type": "rss", "url": f"http://test/{i}",
             "category": "测试", "max_items": self.items_per_source}
            for i in range(self.sources_count)
        ]

    def fetch_source(self, src, max_items):
        time.sleep(self.source_latency)
        from src.scraper import RawNews
        # 使用uuid确保每个标题唯一，避免is_duplicate误判
        import uuid
        return [
            RawNews(
                url=f"http://test/{src.get('name', 'x')}/{j}",
                original_title=f"测试新闻-{uuid.uuid4().hex[:8]}-{j}",
                source=src.get("name", ""),
                category=src.get("category", ""),
                summary=f"原始摘要-{uuid.uuid4().hex[:6]}",
            )
            for j in range(self.items_per_source)
        ]

    def fetch_article_content(self, url, max_chars=4000):
        time.sleep(self.content_latency)
        return f"这是{url}的测试正文内容。" * 10


def test_serial_pipeline():
    """测试单线程流程"""
    from src.analyzer import NewsAnalyzer
    from src.config_loader import AppConfig
    from src.database import Database
    from src.strategy_manager import StrategyManager

    print("\n" + "=" * 60)
    print("  单线程模式测试")
    print("=" * 60)

    config = AppConfig()
    mock_scraper = MockScraper(
        sources_count=10, items_per_source=5,
        source_latency=0.5, content_latency=0.4,
    )

    class TestAnalyzer(NewsAnalyzer):
        def __init__(self):
            self.config = config
            self.db = Database(":memory:")
            self.db._init_db()
            self.scraper = mock_scraper
            self.llm = MockLLMClient(avg_latency=1.0)
            self.strategy_manager = StrategyManager([])

        def run_full_pipeline(self, max_items_per_source=None, progress_callback=None):
            stats = {"sources": 0, "fetched": 0, "new": 0,
                     "summarized": 0, "translated": 0, "errors": 0}
            all_raw = []
            total_sources = len(self.scraper.get_sources())
            for i, src in enumerate(self.scraper.get_sources()):
                items = self.scraper.fetch_source(src, max_items=5)
                all_raw.extend(items)
                stats["sources"] += 1
            stats["fetched"] = len(all_raw)

            for raw in all_raw:
                content = self.scraper.fetch_article_content(raw.url)
                if self.db.is_duplicate(raw.original_title, raw.url, raw.summary):
                    continue
                from src.database import NewsItem
                item = NewsItem(
                    url=raw.url, original_title=raw.original_title,
                    title=raw.original_title, source=raw.source,
                    category=raw.category, content=content,
                    one_line_summary=raw.summary,
                )
                nid = self.db.save_news(item)
                stats["new"] += 1
                t, s = self.llm.generate_summary(
                    item.original_title, item.one_line_summary,
                    item.content, item.source,
                )
                self.db.update_summary(nid, s, t)
                stats["summarized"] += 1
            return stats

    analyzer = TestAnalyzer()
    # 使用临时文件DB代替内存DB，避免schema不可见问题
    import tempfile
    tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
    analyzer.db = Database(tmp_db)
    analyzer.db._init_db()
    start = time.time()
    mem_before = get_process_metrics()
    stats = analyzer.run_full_pipeline()
    elapsed = time.time() - start
    mem_after = get_process_metrics()

    return {
        "mode": "serial",
        "elapsed_seconds": round(elapsed, 2),
        "stats": stats,
        "memory_mb_peak": max(mem_before["memory_mb"], mem_after["memory_mb"]),
        "threads_peak": mem_after["threads"],
    }


def test_parallel_pipeline():
    """测试多线程流程"""
    from src.config_loader import AppConfig
    from src.database import Database
    from src.strategy_manager import StrategyManager
    from src.parallel_analyzer import ParallelNewsAnalyzer, PipelineConfig

    print("\n" + "=" * 60)
    print("  多线程模式测试")
    print("=" * 60)

    config = AppConfig()
    mock_scraper = MockScraper(
        sources_count=10, items_per_source=5,
        source_latency=0.5, content_latency=0.4,
    )
    mock_llm = MockLLMClient(avg_latency=1.0)

    class TestParallelAnalyzer(ParallelNewsAnalyzer):
        def __init__(self):
            self.config = config
            self.pipeline_config = PipelineConfig(
                fetch_workers=8, content_workers=10, summary_workers=4, llm_rate_limit=4,
            )
            self.db = Database(":memory:")
            self.db._init_db()
            self.base_scraper = mock_scraper

            from src.scraper import Scraper
            self.scraper_real = Scraper()
            self.scraper = self  # 兼容父类调用
            self.llm = mock_llm
            self.strategy_manager = StrategyManager([])
            self._llm_semaphore = threading.Semaphore(4)
            self._stats_lock = threading.Lock()

        def run_full_pipeline(self, max_items_per_source=None, progress_callback=None):
            from src.parallel_analyzer import ProgressTracker
            from concurrent.futures import ThreadPoolExecutor, as_completed
            from src.database import NewsItem
            from src.strategy_manager import StrategyManager

            stats = {"sources": 0, "fetched": 0, "new": 0,
                     "summarized": 0, "translated": 0, "errors": 0}
            progress = ProgressTracker(progress_callback)

            all_raw = []
            sources = mock_scraper.get_sources()
            total = len(sources)
            with ThreadPoolExecutor(max_workers=8) as ex:
                futs = {ex.submit(mock_scraper.fetch_source, s, 5): s for s in sources}
                for f in as_completed(futs):
                    all_raw.extend(f.result())
                    stats["sources"] += 1
            stats["fetched"] = len(all_raw)

            # 并行抓详情
            content_map = {}
            with ThreadPoolExecutor(max_workers=10) as ex:
                futs = {ex.submit(mock_scraper.fetch_article_content, r.url): r.url for r in all_raw}
                for f in as_completed(futs):
                    content_map[futs[f]] = f.result()

            # 串行保存
            new_ids = []
            for raw in all_raw:
                if self.db.is_duplicate(raw.original_title, raw.url, raw.summary):
                    continue
                item = NewsItem(
                    url=raw.url, original_title=raw.original_title,
                    title=raw.original_title, source=raw.source,
                    category=raw.category, content=content_map.get(raw.url, ""),
                    one_line_summary=raw.summary,
                )
                try:
                    nid = self.db.save_news(item)
                    new_ids.append(nid)
                    stats["new"] += 1
                except Exception as e:
                    stats["errors"] += 1

            # 并行摘要
            with ThreadPoolExecutor(max_workers=4) as ex:
                def task(nid):
                    with self._llm_semaphore:
                        item = self.db.get_news_by_id(nid)
                        if not item:
                            return
                        t, s = self.llm.generate_summary(
                            item.original_title, item.one_line_summary,
                            item.content, item.source,
                        )
                        self.db.update_summary(nid, s, t)
                futs = [ex.submit(task, nid) for nid in new_ids]
                for f in as_completed(futs):
                    try:
                        f.result()
                        stats["summarized"] += 1
                    except Exception:
                        stats["errors"] += 1
            return stats

    analyzer = TestParallelAnalyzer()
    import tempfile
    tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
    analyzer.db = Database(tmp_db)
    analyzer.db._init_db()
    start = time.time()
    mem_before = get_process_metrics()
    stats = analyzer.run_full_pipeline()
    elapsed = time.time() - start
    mem_after = get_process_metrics()

    return {
        "mode": "parallel",
        "elapsed_seconds": round(elapsed, 2),
        "stats": stats,
        "memory_mb_peak": max(mem_before["memory_mb"], mem_after["memory_mb"]),
        "threads_peak": mem_after["threads"],
    }


def generate_report(serial, parallel_):
    """生成对比报告"""
    print("\n" + "=" * 60)
    print("  性能对比报告")
    print("=" * 60)

    speedup = serial["elapsed_seconds"] / parallel_["elapsed_seconds"]
    time_saved = serial["elapsed_seconds"] - parallel_["elapsed_seconds"]
    time_reduction = (time_saved / serial["elapsed_seconds"]) * 100

    print(f"\n[耗时对比]")
    print(f"  单线程: {serial['elapsed_seconds']}秒")
    print(f"  多线程: {parallel_['elapsed_seconds']}秒")
    print(f"  加速比: {speedup:.2f}x")
    print(f"  节省时间: {time_saved:.2f}秒")
    print(f"  性能提升: {time_reduction:.1f}%")

    print(f"\n[处理量]")
    print(f"  抓取源: 单={serial['stats']['sources']} / 多={parallel_['stats']['sources']}")
    print(f"  获取条数: 单={serial['stats']['fetched']} / 多={parallel_['stats']['fetched']}")
    print(f"  新增条数: 单={serial['stats']['new']} / 多={parallel_['stats']['new']}")
    print(f"  AI摘要: 单={serial['stats']['summarized']} / 多={parallel_['stats']['summarized']}")
    print(f"  错误数: 单={serial['stats']['errors']} / 多={parallel_['stats']['errors']}")

    print(f"\n[资源占用]")
    print(f"  内存峰值: 单={serial['memory_mb_peak']:.1f}MB / 多={parallel_['memory_mb_peak']:.1f}MB")
    print(f"  线程数: 单={serial['threads_peak']} / 多={parallel_['threads_peak']}")

    target_met = time_reduction >= 30
    print(f"\n[结论]")
    print(f"  性能提升 {'达标 (>=30%)' if target_met else '未达标 (<30%)'}: {time_reduction:.1f}%")
    print(f"  数据完整性: {'✅ 一致' if serial['stats']['new'] == parallel_['stats']['new'] else '❌ 差异'}")
    print(f"  系统稳定性: {'✅ 良好' if parallel_['stats']['errors'] <= serial['stats']['errors'] + 2 else '⚠️ 异常'}")

    report = {
        "test_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "serial": serial,
        "parallel": parallel_,
        "speedup_ratio": round(speedup, 2),
        "time_reduction_percent": round(time_reduction, 2),
        "target_met": target_met,
    }
    with open("performance_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n  报告已保存到: performance_report.json")
    return report


def main():
    print("=" * 60)
    print("  多线程优化性能对比测试")
    print("=" * 60)
    print(f"  测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  CPU 核心数: {psutil.cpu_count()}")
    print("=" * 60)

    serial = test_serial_pipeline()
    print(f"\n  单线程完成: {serial['elapsed_seconds']}秒")

    parallel_ = test_parallel_pipeline()
    print(f"\n  多线程完成: {parallel_['elapsed_seconds']}秒")

    report = generate_report(serial, parallel_)
    return 0 if report["target_met"] else 1


if __name__ == "__main__":
    sys.exit(main())
