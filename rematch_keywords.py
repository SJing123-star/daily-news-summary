"""
重新匹配脚本：根据新的关键词匹配策略对现有新闻进行重新匹配
匹配规则：
1. 所有新闻使用中文关键词匹配
2. 英文标题先翻译为中文再匹配
3. 仅匹配标题，不匹配正文和摘要
"""
import os
import sys
import json
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.database import Database
from src.strategy_manager import StrategyManager
from src.config_loader import AppConfig
from src.llm_client import LLMClient


def is_english(text: str) -> bool:
    if not text:
        return False
    ascii_chars = sum(1 for c in text if ord(c) < 128)
    return ascii_chars > len(text) * 0.8


def get_strategy_for_source(strategy_manager, source_name, category):
    """根据新闻源名称和分类获取合适的策略"""
    source_name_lower = source_name.lower()
    
    category_strategy_map = {
        "网络安全": "cybersecurity",
        "科技": "technology",
        "政治": "chinese",
        "经济": "chinese",
    }
    
    if category in category_strategy_map:
        strategy = strategy_manager.get_strategy(category_strategy_map[category])
        if strategy:
            return strategy
    
    if "darkreading" in source_name_lower or "securityweek" in source_name_lower or "hacker" in source_name_lower:
        strategy = strategy_manager.get_strategy("cybersecurity")
        if strategy:
            return strategy
    
    if "36kr" in source_name_lower or "tech" in source_name_lower:
        strategy = strategy_manager.get_strategy("technology")
        if strategy:
            return strategy
    
    return strategy_manager.get_strategy("chinese") or strategy_manager.get_default_strategy()


def main():
    print("="*60)
    print("关键词匹配策略重新匹配脚本")
    print("="*60)
    print(f"运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    config = AppConfig()
    strategies_config = config.strategies
    
    print("加载策略配置:")
    for s in strategies_config:
        print(f"  - {s['name']} ({s['site_type']})")
    print()

    strategy_manager = StrategyManager(strategies_config)
    
    llm = LLMClient(
        provider=config.llm_provider,
        api_key=config.llm_api_key,
        model=config.llm_model,
        base_url=config.llm_base_url,
    )

    db = Database()

    print("获取所有新闻记录...")
    news_list = db.get_recent_news(limit=10000, days=3650)
    print(f"共获取 {len(news_list)} 条新闻")
    print()

    stats = {
        "total": 0,
        "matched": 0,
        "not_matched": 0,
        "updated": 0,
        "translated": 0,
        "strategies_used": {},
        "categories_updated": {},
    }

    print("开始重新匹配...")
    print("说明: 英文标题先翻译为中文，仅匹配标题，使用中文关键词")
    print("-"*60)
    
    for news in news_list:
        stats["total"] += 1
        
        match_title = news.original_title or news.title
        
        if is_english(match_title):
            retries = 3
            delay = 1
            for attempt in range(retries):
                try:
                    translated = llm.translate_title(match_title)
                    if translated and translated != match_title and translated.strip():
                        match_title = translated.strip()
                        stats["translated"] += 1
                    break
                except Exception as e:
                    if attempt < retries - 1:
                        time.sleep(delay)
                        delay *= 2
            time.sleep(0.5)
        
        strategy = get_strategy_for_source(strategy_manager, news.source, news.category)
        
        is_match, weight, matched_kws = strategy.match(match_title, "")

        stats["strategies_used"][strategy.site_type] = stats["strategies_used"].get(strategy.site_type, 0) + 1

        old_strategy_matched = news.is_strategy_matched
        new_strategy_matched = 1 if is_match else 0
        
        if old_strategy_matched != new_strategy_matched:
            stats["updated"] += 1
            db.update_news_strategy_matched_batch([(new_strategy_matched, news.id)])
            stats["categories_updated"][news.category] = stats["categories_updated"].get(news.category, 0) + 1

        if is_match:
            stats["matched"] += 1
            if stats["matched"] <= 10:
                print(f"✅ 匹配: {match_title[:60]}...")
                print(f"   策略: {strategy.name}, 权重: {weight:.4f}, 关键词: {matched_kws}")
        else:
            stats["not_matched"] += 1

        if stats["total"] % 50 == 0:
            print(f"进度: {stats['total']}/{len(news_list)} (匹配: {stats['matched']}, 翻译: {stats['translated']})")

    print("-"*60)
    print()

    print("匹配结果统计:")
    print("-"*60)
    print(f"总新闻数: {stats['total']}")
    print(f"翻译数量: {stats['translated']} ({stats['translated']/stats['total']*100:.1f}%)")
    print(f"匹配成功: {stats['matched']} ({stats['matched']/stats['total']*100:.1f}%)")
    print(f"匹配失败: {stats['not_matched']} ({stats['not_matched']/stats['total']*100:.1f}%)")
    print(f"状态变更: {stats['updated']}")
    print()

    print("策略使用情况:")
    for strategy_type, count in stats["strategies_used"].items():
        strategy_name = strategy_manager.get_strategy(strategy_type)
        name = strategy_name.name if strategy_name else strategy_type
        print(f"  - {name}: {count} 条")
    print()

    print("分类更新情况:")
    for category, count in stats["categories_updated"].items():
        print(f"  - {category}: {count} 条状态变更")

    report = {
        "run_time": datetime.now().isoformat(),
        "total_news": stats["total"],
        "translated": stats["translated"],
        "matched": stats["matched"],
        "not_matched": stats["not_matched"],
        "updated": stats["updated"],
        "strategies_used": stats["strategies_used"],
        "categories_updated": stats["categories_updated"],
    }
    report_path = f"rematch_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print()
    print(f"报告已保存到: {report_path}")
    print()
    print("✅ 重新匹配完成!")


if __name__ == "__main__":
    main()
