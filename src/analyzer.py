import logging
import time
from typing import List, Dict, Any

from .config_loader import AppConfig
from .database import Database, NewsItem
from .scraper import Scraper, RawNews
from .llm_client import LLMClient
from .strategy_manager import StrategyManager

logger = logging.getLogger(__name__)


class NewsAnalyzer:
    def __init__(self, config: AppConfig = None):
        if config is None:
            config = AppConfig()
        self.config = config
        self.db = Database()
        self.scraper = Scraper(
            min_title_length=config.min_title_length,
            keywords=config.keywords,
        )
        self.llm = LLMClient(
            provider=config.llm_provider,
            api_key=config.llm_api_key,
            model=config.llm_model,
            base_url=config.llm_base_url,
        )
        self.strategy_manager = StrategyManager(config.strategies)

    def run_full_pipeline(self, max_items_per_source: int = None, progress_callback=None) -> Dict[str, Any]:
        stats = {"sources": 0, "fetched": 0, "new": 0, "summarized": 0, "translated": 0, "errors": 0}

        max_items = max_items_per_source or self.config.max_news_per_source
        all_raw: List[RawNews] = []

        total_sources = len(self.config.news_sources)

        enabled_sources = [src for src in self.config.news_sources if src.get("enabled", True)]
        total_sources = len(enabled_sources)
        
        for i, src in enumerate(enabled_sources):
            try:
                if progress_callback:
                    progress_callback(
                        "fetching",
                        f"正在抓取 [{i+1}/{total_sources}] {src.get('name')}...",
                        int((i / total_sources) * 25),
                        stats,
                    )
                items = self.scraper.fetch_source(src, max_items=max_items)
                all_raw.extend(items)
                stats["sources"] += 1
            except Exception as e:
                logger.error(f"源 {src.get('name')} 抓取异常: {e}")
                stats["errors"] += 1

        stats["fetched"] = len(all_raw)

        if progress_callback:
            progress_callback("fetching", f"抓取完成，共获取 {len(all_raw)} 条新闻", 25, stats)

        new_ids = []
        for i, raw in enumerate(all_raw):
            try:
                if self.db.is_duplicate(raw.original_title, raw.url, raw.summary):
                    logger.debug(f"跳过重复新闻: {raw.original_title}")
                    continue
                if progress_callback:
                    progress_callback(
                        "saving",
                        f"正在保存新闻 [{i+1}/{len(all_raw)}]...",
                        25 + int((i / len(all_raw)) * 15),
                        stats,
                    )
                content = self.scraper.fetch_article_content(raw.url, max_chars=4000)
                is_keyword_match = self._is_keyword_match(raw.original_title, raw.summary, raw.url)
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
                stats["new"] += 1
            except Exception as e:
                logger.error(f"保存新闻失败: {e}")
                stats["errors"] += 1

        if progress_callback:
            progress_callback("summarizing", f"开始AI生成中文摘要，共 {len(new_ids)} 条...", 40, stats)

        for i, news_id in enumerate(new_ids):
            try:
                item = self.db.get_news_by_id(news_id)
                if not item:
                    continue
                if progress_callback:
                    progress_callback(
                        "summarizing",
                        f"正在生成摘要 [{i+1}/{len(new_ids)}]...",
                        40 + int((i / len(new_ids)) * 60),
                        stats,
                    )
                title, summary = self.llm.generate_summary(
                    item.original_title, item.one_line_summary, item.content, item.source
                )
                self.db.update_summary(news_id, summary, title)
                stats["summarized"] += 1
                time.sleep(0.3)
            except Exception as e:
                logger.error(f"生成摘要失败 id={news_id}: {e}")
                stats["errors"] += 1

        logger.info(f"完成: {stats}")
        return stats

    def _is_keyword_match(self, title: str, summary: str, url: str = "") -> bool:
        if not self.config.keywords:
            return True
        is_match, weight, matched_kws, strategy_type = self.strategy_manager.match(url, title, summary)
        logger.debug(f"策略匹配: url={url}, strategy={strategy_type}, match={is_match}, weight={weight}, kws={matched_kws}")
        return is_match

    def generate_analysis_for(self, news_id: int) -> str:
        item = self.db.get_news_by_id(news_id)
        if not item:
            return "未找到该新闻"

        if item.is_analysis_done and item.analysis_brief:
            return item.analysis_brief

        brief = self.llm.generate_analysis(
            item.original_title, item.one_line_summary, item.content, item.source
        )
        if brief and brief != "分析服务暂不可用。建议检查 API Key 配置或稍后重试。":
            self.db.update_analysis(news_id, brief)
        return brief

    def retry_pending_summaries(self, limit: int = 10) -> int:
        items = self.db.get_pending_summary(limit=limit)
        count = 0
        for item in items:
            try:
                title, summary = self.llm.generate_summary(
                    item.original_title, item.one_line_summary, item.content, item.source
                )
                self.db.update_summary(item.id, summary, title)
                count += 1
                time.sleep(0.3)
            except Exception as e:
                logger.error(f"重试摘要失败 id={item.id}: {e}")
        return count
