# -*- coding: utf-8 -*-
"""专项网络安全新闻抓取脚本"""

import sys
sys.path.insert(0, '.')

import time
from src.config_loader import AppConfig
from src.analyzer import NewsAnalyzer
from src.database import Database

def fetch_cybersecurity_news():
    config = AppConfig()
    db = Database()

    # 筛选网络安全新闻源
    cyber_sources = [s for s in config.news_sources if s.get('category') == '网络安全']

    print("=" * 60)
    print("专项网络安全新闻抓取任务")
    print("=" * 60)
    print(f"\n配置参数:")
    print(f"  - 新闻源数量: {len(cyber_sources)}")
    print(f"  - 抓取时间范围: 过去 {config.fetch_hours} 小时")
    print(f"  - 默认每源最大条数: {config.max_news_per_source}")

    print(f"\n新闻源列表:")
    for src in cyber_sources:
        max_items = src.get('max_items', config.max_news_per_source)
        print(f"  - {src['name']}")
        print(f"    URL: {src['url']}")
        print(f"    最大抓取: {max_items} 条")

    # 创建分析器
    analyzer = NewsAnalyzer(config)

    # 进度回调
    def progress_callback(status, message, progress, stats):
        print(f"\n[{progress:3d}%] [{status.upper()}] {message}")
        if stats:
            print(f"    统计: 抓取{stats.get('fetched',0)} ，新增{stats.get('new',0)}，摘要{stats.get('summarized',0)}，翻译{stats.get('translated',0)}，错误{stats.get('errors',0)}")

    print("\n" + "=" * 60)
    print("开始抓取...")
    print("=" * 60)

    # 执行抓取
    stats = analyzer.run_full_pipeline(max_items_per_source=None, progress_callback=progress_callback)

    print("\n" + "=" * 60)
    print("抓取完成！")
    print("=" * 60)

    print("\n最终统计:")
    print(f"  - 新闻源数量: {stats['sources']}")
    print(f"  - 抓取总数: {stats['fetched']}")
    print(f"  - 新增新闻: {stats['new']}")
    print(f"  - 翻译标题: {stats['translated']}")
    print(f"  - AI摘要: {stats['summarized']}")
    print(f"  - 错误数: {stats['errors']}")

    # 查询网络安全类新闻
    print("\n" + "=" * 60)
    print("数据完整性校验")
    print("=" * 60)

    conn = db.get_connection()
    cursor = conn.cursor()

    # 按分类统计
    cursor.execute("""
        SELECT category, COUNT(*) as count
        FROM news
        GROUP BY category
        ORDER BY count DESC
    """)
    print("\n各分类新闻数量:")
    for row in cursor.fetchall():
        cat = row[0] or '未分类'
        cnt = row[1]
        marker = " <-- 网络安全" if cat == "网络安全" else ""
        print(f"  - {cat}: {cnt} 条{marker}")

    # 网络安全新闻详情
    cursor.execute("""
        SELECT id, title, source, publish_time, is_summary_done, is_highlighted
        FROM news
        WHERE category = '网络安全'
        ORDER BY publish_time DESC
        LIMIT 50
    """)
    rows = cursor.fetchall()

    print(f"\n网络安全新闻详情 (共 {len(rows)} 条):")
    print("-" * 80)

    for i, row in enumerate(rows[:20], 1):
        news_id, title, source, pub_time, is_sum, is_high = row
        pub_str = pub_time.strftime('%Y-%m-%d %H:%M') if pub_time else '未知'
        sum_flag = "✓" if is_sum else "○"
        high_flag = "★" if is_high else ""
        print(f"\n{i}. {title}")
        print(f"   来源: {source} | 时间: {pub_str}")
        print(f"   摘要: {sum_flag} | 高亮: {high_flag}")

    conn.close()

    return stats

if __name__ == "__main__":
    try:
        fetch_cybersecurity_news()
        print("\n任务执行完成！")
    except Exception as e:
        print(f"\n执行出错: {e}")
        import traceback
        traceback.print_exc()
