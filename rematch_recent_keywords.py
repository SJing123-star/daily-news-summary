"""
重新匹配脚本：对最近一个月的数据重新进行关键词匹配
优化点：
1. 只处理最近一个月的数据
2. 如果文章已经翻译了（title != original_title），直接使用翻译后的标题匹配
3. 使用新闻源配置的策略类型进行匹配
4. 使用修复后的单词边界匹配逻辑
"""
import os
import sys
import json
import time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.database import Database
from src.strategy_manager import StrategyManager
from src.config_loader import AppConfig
from src.llm_client import LLMClient


def is_english(text: str) -> bool:
    """判断是否为英文文本"""
    if not text:
        return False
    ascii_chars = sum(1 for c in text if ord(c) < 128)
    return ascii_chars > len(text) * 0.8


def get_strategy_for_source(strategy_manager, source_name, config):
    """根据新闻源名称获取配置的策略类型"""
    # 遍历新闻源配置，查找匹配的策略类型
    for src in config.news_sources:
        if src.get("name") == source_name:
            strategy_type = src.get("strategy", "")
            if strategy_type:
                return strategy_manager.get_strategy_for_site_type(strategy_type)
    
    # 如果没有找到，使用默认策略
    return strategy_manager.get_default_strategy()


def get_recent_news(db, days=30):
    """获取最近指定天数的新闻"""
    one_month_ago = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    print(f"获取 {one_month_ago} 之后的新闻...")
    
    with db._get_conn() as conn:
        rows = conn.execute("""
            SELECT * FROM news
            WHERE created_at >= ?
            ORDER BY id DESC
        """, (one_month_ago,)).fetchall()
    
    return [db._row_to_item(row) for row in rows]


def main():
    print("="*60)
    print("关键词匹配策略重新匹配脚本（最近一个月）")
    print("="*60)
    print(f"运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    config = AppConfig()
    strategy_manager = StrategyManager(config.strategies)
    
    llm = LLMClient(
        provider=config.llm_provider,
        api_key=config.llm_api_key,
        model=config.llm_model,
        base_url=config.llm_base_url,
    )

    db = Database()

    # 获取最近一个月的新闻
    news_list = get_recent_news(db, days=30)
    print(f"共获取 {len(news_list)} 条新闻")
    print()

    stats = {
        "total": 0,
        "matched": 0,
        "not_matched": 0,
        "updated": 0,
        "translated": 0,
        "already_translated": 0,
        "strategies_used": {},
        "categories_updated": {},
    }

    print("开始重新匹配...")
    print("说明: 已翻译的文章直接使用翻译后的标题匹配，未翻译的英文标题直接匹配（LLM服务不可用）")
    print("-"*60)
    
    for news in news_list:
        stats["total"] += 1
        
        original_title = news.original_title or ""
        translated_title = news.title or ""
        
        # 判断是否已经翻译过
        if translated_title and translated_title != original_title:
            # 已经翻译过，直接使用翻译后的标题
            match_title = translated_title
            stats["already_translated"] += 1
        elif is_english(original_title):
            # 未翻译且是英文标题，直接使用英文标题匹配（LLM服务不可用）
            match_title = original_title
            stats["translated"] += 1  # 标记为需要翻译但未翻译
        else:
            # 中文标题，直接使用
            match_title = original_title
        
        # 获取策略
        strategy = get_strategy_for_source(strategy_manager, news.source, config)
        
        # 进行匹配
        is_match, weight, matched_kws = strategy.match(match_title, news.one_line_summary or "")

        stats["strategies_used"][strategy.site_type] = stats["strategies_used"].get(strategy.site_type, 0) + 1

        old_strategy_matched = news.is_strategy_matched
        new_strategy_matched = 1 if is_match else 0
        
        if old_strategy_matched != new_strategy_matched:
            stats["updated"] += 1
            db.update_news_strategy_matched_batch([(new_strategy_matched, news.id)])
            # 同时更新 is_highlighted 字段
            with db._get_conn() as conn:
                conn.execute("UPDATE news SET is_highlighted = ? WHERE id = ?", (new_strategy_matched, news.id))
                conn.commit()
            stats["categories_updated"][news.category] = stats["categories_updated"].get(news.category, 0) + 1

        if is_match:
            stats["matched"] += 1
            if stats["matched"] <= 10:
                print(f"✅ 匹配: {match_title[:60]}...")
                print(f"   来源: {news.source}, 策略: {strategy.name}, 关键词: {matched_kws}")
        else:
            stats["not_matched"] += 1

        if stats["total"] % 50 == 0:
            print(f"进度: {stats['total']}/{len(news_list)} (匹配: {stats['matched']}, 新翻译: {stats['translated']}, 已翻译: {stats['already_translated']})")

    print("-"*60)
    print()

    print("匹配结果统计:")
    print("-"*60)
    print(f"总新闻数: {stats['total']}")
    print(f"已翻译复用: {stats['already_translated']} ({stats['already_translated']/stats['total']*100:.1f}%)")
    print(f"本次翻译: {stats['translated']} ({stats['translated']/stats['total']*100:.1f}%)")
    print(f"匹配成功: {stats['matched']} ({stats['matched']/stats['total']*100:.1f}%)")
    print(f"匹配失败: {stats['not_matched']} ({stats['not_matched']/stats['total']*100:.1f}%)")
    print(f"状态变更: {stats['updated']}")
    print()

    print("策略使用情况:")
    for strategy_type, count in stats["strategies_used"].items():
        print(f"  - {strategy_type}: {count} 条")
    print()

    print("分类更新情况:")
    for category, count in stats["categories_updated"].items():
        print(f"  - {category}: {count} 条状态变更")

    report = {
        "run_time": datetime.now().isoformat(),
        "total_news": stats["total"],
        "already_translated": stats["already_translated"],
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
