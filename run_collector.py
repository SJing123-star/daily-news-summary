"""国内外大事一键收集脚本

用法:
    python run_collector.py              # 运行完整流水线
    python run_collector.py --items 15   # 每源最多抓取 15 条
"""

import argparse
import logging
import os
import sys
import time

log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(log_dir, "collector.log"), encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)

logger = logging.getLogger("run_collector")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config_loader import AppConfig
from src.analyzer import NewsAnalyzer


def main():
    parser = argparse.ArgumentParser(description="国内外大事一键收集工具")
    parser.add_argument("--items", type=int, default=None,
                        help="每个新闻源最多抓取条数（覆盖 config.yaml）")
    parser.add_argument("--retry", action="store_true",
                        help="重试未完成摘要的新闻")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("启动新闻收集服务...")
    t0 = time.time()

    try:
        config = AppConfig()
        logger.info(f"配置: {len(config.news_sources)} 个新闻源, LLM: {config.llm_provider}/{config.llm_model}")
    except Exception as e:
        logger.error(f"配置加载失败: {e}")
        return 1

    analyzer = NewsAnalyzer(config=config)

    if args.retry:
        logger.info("开始重试待处理摘要...")
        count = analyzer.retry_pending_summaries(limit=20)
        logger.info(f"重试完成, 成功 {count} 条")
        return 0

    stats = analyzer.run_full_pipeline(max_items_per_source=args.items)

    dt = time.time() - t0
    logger.info("=" * 60)
    logger.info(f"执行完成 用时 {dt:.1f}s")
    logger.info(f"统计: 处理源={stats['sources']}  抓取={stats['fetched']}  "
                f"新增入库={stats['new']}  AI 摘要={stats['summarized']}  错误={stats['errors']}")

    db_stats = analyzer.db.get_stats()
    logger.info(f"数据库: 总条数={db_stats['total']}  已摘要={db_stats['summarized']}  "
                f"已分析={db_stats['analyzed']}")
    logger.info("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
