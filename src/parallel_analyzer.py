"""
多线程新闻分析器
通过并行化抓取、详情提取、AI摘要三个阶段提升处理速度
"""
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed, Future
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Callable, Tuple
import threading

from .config_loader import AppConfig
from .database import Database, NewsItem
from .scraper import Scraper, RawNews
from .llm_client import LLMClient
from .strategy_manager import StrategyManager
from .utils import is_english

logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    """流水线并发配置"""
    fetch_workers: int = 8            # 新闻源并行抓取
    content_workers: int = 10         # 文章详情并行抓取
    summary_workers: int = 2          # AI摘要并行生成（降低以避免API限流）
    llm_rate_limit: int = 2           # LLM调用并发上限（降低以避免API限流）
    llm_request_interval: float = 0.5 # LLM请求间隔（秒），避免短时间内大量请求
    enable_parallel: bool = True      # 是否启用并行


class ThreadSafeDatabase:
    """线程安全的数据库包装器"""

    def __init__(self, db: Database):
        self._db = db
        self._lock = threading.Lock()

    def is_duplicate(self, title: str, url: str = "", summary: str = "", threshold: float = 0.8) -> bool:
        with self._lock:
            return self._db.is_duplicate(title, url, summary, threshold)

    def save_news(self, item: NewsItem) -> int:
        with self._lock:
            return self._db.save_news(item)

    def update_summary(self, news_id: int, one_line_summary: str, title: str = ""):
        with self._lock:
            self._db.update_summary(news_id, one_line_summary, title)

    def get_news_by_id(self, news_id: int) -> Optional[NewsItem]:
        with self._lock:
            return self._db.get_news_by_id(news_id)

    def update_analysis(self, news_id: int, analysis_brief: str):
        """添加缺失的线程安全包装方法"""
        with self._lock:
            self._db.update_analysis(news_id, analysis_brief)

    def get_pending_summary(self, limit: int = 20) -> List[NewsItem]:
        """添加缺失的线程安全包装方法"""
        with self._lock:
            return self._db.get_pending_summary(limit)


class ThreadSafeScraper:
    """线程安全的抓取器包装器（requests.Session 本身是线程安全的）"""

    def __init__(self, scraper: Scraper):
        self._scraper = scraper
        # requests.Session 在多线程下读写不安全，需要每个线程独立
        self._local = threading.local()

    def _get_scraper(self) -> Scraper:
        if not hasattr(self._local, "scraper"):
            self._local.scraper = Scraper(
                min_title_length=self._scraper.min_title_length,
                keywords=self._scraper.keywords,
            )
        return self._local.scraper

    def fetch_source(self, source_cfg: Dict[str, Any], max_items: int) -> List[RawNews]:
        return self._get_scraper().fetch_source(source_cfg, max_items)

    def fetch_article_content(self, url: str, max_chars: int = 4000) -> str:
        return self._get_scraper().fetch_article_content(url, max_chars)


class ProgressTracker:
    """线程安全的进度跟踪器"""

    def __init__(self, callback: Optional[Callable] = None):
        self._lock = threading.Lock()
        self._callback = callback

    def update(self, stage: str, message: str, percent: int, stats: Dict[str, Any]):
        with self._lock:
            if self._callback:
                try:
                    self._callback(stage, message, percent, dict(stats))
                except Exception as e:
                    logger.warning(f"进度回调异常: {e}")


class ParallelNewsAnalyzer:
    """多线程新闻分析器"""

    def __init__(
        self,
        config: AppConfig = None,
        pipeline_config: PipelineConfig = None,
    ):
        if config is None:
            config = AppConfig()
        self.config = config
        self.pipeline_config = pipeline_config or PipelineConfig()

        self.db = ThreadSafeDatabase(Database())
        self.base_scraper = Scraper(
            min_title_length=config.min_title_length,
            keywords=config.keywords,
        )
        self.scraper = ThreadSafeScraper(self.base_scraper)
        self.llm = LLMClient(
            provider=config.llm_provider,
            api_key=config.llm_api_key,
            model=config.llm_model,
            base_url=config.llm_base_url,
        )
        self.strategy_manager = StrategyManager(config.strategies)
        self._llm_semaphore = threading.Semaphore(self.pipeline_config.llm_rate_limit)
        self._stats_lock = threading.Lock()

    def run_full_pipeline(
        self,
        max_items_per_source: int = None,
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """执行完整的多线程流水线"""
        progress = ProgressTracker(progress_callback)
        stats: Dict[str, Any] = {
            "sources": 0, "fetched": 0, "new": 0,
            "summarized": 0, "translated": 0, "errors": 0,
        }
        start_time = time.time()

        max_items = max_items_per_source or self.config.max_news_per_source

        # ========== 阶段1：并行抓取所有新闻源 ==========
        progress.update("fetching", "开始并行抓取新闻源...", 0, stats)
        all_raw = self._parallel_fetch_sources(max_items, progress, stats)

        # ========== 阶段2：并行抓取文章详情 ==========
        progress.update("fetching", f"抓取完成，共获取 {len(all_raw)} 条，开始抓取详情...", 25, stats)
        content_map = self._parallel_fetch_content(all_raw, progress, stats)

        # ========== 阶段3：批量保存新闻（加DB锁） ==========
        progress.update("saving", "正在保存新闻到数据库...", 35, stats)
        new_ids = self._save_news_batch(all_raw, content_map, progress, stats)

        # ========== 阶段4：并行生成AI摘要 ==========
        progress.update("summarizing", f"开始并行生成AI摘要，共 {len(new_ids)} 条...", 45, stats)
        self._parallel_summarize(new_ids, progress, stats)

        elapsed = time.time() - start_time
        stats["elapsed_seconds"] = round(elapsed, 2)
        logger.info(f"多线程流水线完成，耗时 {elapsed:.2f} 秒: {stats}")
        progress.update("done", f"完成！耗时 {elapsed:.2f} 秒", 100, stats)
        return stats

    def _parallel_fetch_sources(
        self,
        max_items: int,
        progress: ProgressTracker,
        stats: Dict[str, Any],
    ) -> List[RawNews]:
        """并行抓取所有新闻源"""
        all_raw: List[RawNews] = []
        enabled_sources = [src for src in self.config.news_sources if src.get("enabled", True)]
        total_sources = len(enabled_sources)

        with ThreadPoolExecutor(
            max_workers=self.pipeline_config.fetch_workers,
            thread_name_prefix="fetch-",
        ) as executor:
            future_to_src: Dict[Future, Dict[str, Any]] = {}
            for src in enabled_sources:
                future = executor.submit(
                    self._fetch_source_safe, src, max_items
                )
                future_to_src[future] = src

            completed = 0
            for future in as_completed(future_to_src):
                src = future_to_src[future]
                completed += 1
                try:
                    items = future.result()
                    all_raw.extend(items)
                    with self._stats_lock:
                        stats["sources"] += 1
                except Exception as e:
                    logger.error(f"源 {src.get('name')} 抓取异常: {e}")
                    with self._stats_lock:
                        stats["errors"] += 1

                percent = int((completed / total_sources) * 25)
                progress.update(
                    "fetching",
                    f"已抓取 [{completed}/{total_sources}] {src.get('name', '')}",
                    percent, stats,
                )

        with self._stats_lock:
            stats["fetched"] = len(all_raw)
        return all_raw

    def _fetch_source_safe(self, src: Dict[str, Any], max_items: int) -> List[RawNews]:
        """单源抓取的安全包装"""
        try:
            return self.scraper.fetch_source(src, max_items)
        except Exception as e:
            logger.error(f"抓取源 {src.get('name')} 失败: {e}")
            return []

    def _parallel_fetch_content(
        self,
        all_raw: List[RawNews],
        progress: ProgressTracker,
        stats: Dict[str, Any],
    ) -> Dict[str, str]:
        """并行抓取文章详情"""
        content_map: Dict[str, str] = {}
        if not all_raw:
            return content_map

        with ThreadPoolExecutor(
            max_workers=self.pipeline_config.content_workers,
            thread_name_prefix="content-",
        ) as executor:
            future_to_url: Dict[Future, str] = {}
            for raw in all_raw:
                future = executor.submit(
                    self._fetch_content_safe, raw.url
                )
                future_to_url[future] = raw.url

            completed = 0
            total = len(all_raw)
            for future in as_completed(future_to_url):
                url = future_to_url[future]
                completed += 1
                try:
                    content = future.result()
                    content_map[url] = content
                except Exception as e:
                    logger.warning(f"详情抓取失败 {url}: {e}")
                    content_map[url] = ""

                percent = 25 + int((completed / total) * 10)
                progress.update(
                    "fetching",
                    f"详情抓取 [{completed}/{total}]...",
                    percent, stats,
                )

        return content_map

    def _fetch_content_safe(self, url: str) -> str:
        """单URL详情抓取的安全包装"""
        try:
            return self.scraper.fetch_article_content(url, max_chars=4000)
        except Exception as e:
            logger.warning(f"抓取详情失败 {url}: {e}")
            return ""

    def _save_news_batch(
        self,
        all_raw: List[RawNews],
        content_map: Dict[str, str],
        progress: ProgressTracker,
        stats: Dict[str, Any],
    ) -> List[int]:
        """批量保存新闻（带去重和DB锁）"""
        new_ids: List[int] = []
        total = len(all_raw)

        for i, raw in enumerate(all_raw):
            try:
                if self.db.is_duplicate(raw.original_title, raw.url, raw.summary):
                    logger.debug(f"跳过重复新闻: {raw.original_title}")
                    continue

                content = content_map.get(raw.url, "")
                is_keyword_match = self._is_keyword_match(
                    raw.original_title, raw.summary, raw.url, raw.strategy
                )
                item = NewsItem(
                    url=raw.url,
                    original_title=raw.original_title,
                    title=raw.original_title,
                    source=raw.source,
                    category=raw.category,
                    publish_time=raw.publish_time,
                    content=content,
                    one_line_summary=raw.summary or "",
                    analysis_brief="",
                    is_summary_done=0,
                    is_analysis_done=0,
                    is_highlighted=1 if raw.is_highlighted else 0,
                    is_strategy_matched=1 if is_keyword_match else 0,
                )
                news_id = self.db.save_news(item)
                new_ids.append(news_id)
                with self._stats_lock:
                    stats["new"] += 1
            except Exception as e:
                logger.error(f"保存新闻失败: {e}")
                with self._stats_lock:
                    stats["errors"] += 1

            percent = 35 + int((i / max(total, 1)) * 10)
            progress.update(
                "saving",
                f"保存新闻 [{i+1}/{total}]...",
                percent, stats,
            )

        return new_ids

    def _parallel_summarize(
        self,
        new_ids: List[int],
        progress: ProgressTracker,
        stats: Dict[str, Any],
    ):
        """并行生成AI摘要"""
        if not new_ids:
            return

        total = len(new_ids)
        completed = 0

        with ThreadPoolExecutor(
            max_workers=self.pipeline_config.summary_workers,
            thread_name_prefix="summary-",
        ) as executor:
            future_to_id: Dict[Future, int] = {}
            for news_id in new_ids:
                future = executor.submit(
                    self._generate_summary_safe, news_id
                )
                future_to_id[future] = news_id

            for future in as_completed(future_to_id):
                news_id = future_to_id[future]
                completed += 1
                try:
                    result = future.result()
                    if result:
                        with self._stats_lock:
                            stats["summarized"] += 1
                except Exception as e:
                    logger.error(f"生成摘要失败 id={news_id}: {e}")
                    with self._stats_lock:
                        stats["errors"] += 1

                percent = 45 + int((completed / total) * 55)
                progress.update(
                    "summarizing",
                    f"AI摘要 [{completed}/{total}]...",
                    percent, stats,
                )

    def _generate_summary_safe(self, news_id: int) -> bool:
        """单条新闻摘要生成（带LLM限流和请求间隔）"""
        with self._llm_semaphore:
            try:
                item = self.db.get_news_by_id(news_id)
                if not item:
                    return False
                
                time.sleep(self.pipeline_config.llm_request_interval)
                
                title, summary = self.llm.generate_summary(
                    item.original_title, item.one_line_summary,
                    item.content, item.source,
                )
                self.db.update_summary(news_id, summary, title)
                return True
            except Exception as e:
                logger.error(f"生成摘要异常 id={news_id}: {e}")
                return False

    def _is_keyword_match(self, title: str, summary: str, url: str = "", strategy: str = "") -> bool:
        if not self.config.keywords:
            return True
        
        match_title = title
        if is_english(title):
            try:
                match_title = self.llm.translate_title(title)
            except Exception as e:
                logger.warning(f"翻译标题失败: {e}")
                match_title = title
        
        # 优先使用新闻源配置的策略类型
        if strategy:
            strategy_obj = self.strategy_manager.get_strategy_for_site_type(strategy)
            is_match, weight, matched_kws = strategy_obj.match(match_title, summary)
            strategy_type = strategy
        else:
            is_match, weight, matched_kws, strategy_type = self.strategy_manager.match(
                url, match_title, ""
            )
        return is_match

    def generate_analysis_for(self, news_id: int) -> str:
        """单条新闻分析（与NewsAnalyzer保持兼容）"""
        item = self.db.get_news_by_id(news_id)
        if not item:
            return "未找到该新闻"

        if item.is_analysis_done and item.analysis_brief:
            return item.analysis_brief

        with self._llm_semaphore:
            brief = self.llm.generate_analysis(
                item.original_title, item.one_line_summary,
                item.content, item.source,
            )
        if brief and brief != "分析服务暂不可用。建议检查 API Key 配置或稍后重试。":
            self.db.update_analysis(news_id, brief)  # ✅ 使用线程安全包装方法
        return brief

    def retry_pending_summaries(self, limit: int = 10) -> int:
        """重试待摘要新闻（与NewsAnalyzer保持兼容）"""
        items = self.db.get_pending_summary(limit=limit)  # ✅ 使用线程安全包装方法
        if not items:
            return 0

        count = 0
        with ThreadPoolExecutor(
            max_workers=min(self.pipeline_config.summary_workers, len(items)),
            thread_name_prefix="retry-",
        ) as executor:
            futs = [
                executor.submit(self._generate_summary_safe, item.id)
                for item in items
            ]
            for f in as_completed(futs):
                try:
                    if f.result():
                        count += 1
                except Exception as e:
                    logger.error(f"重试摘要失败: {e}")
        return count
