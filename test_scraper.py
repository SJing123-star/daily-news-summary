import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from src.config_loader import AppConfig
from src.scraper import Scraper

c = AppConfig()
scraper = Scraper(min_title_length=c.min_title_length, keywords=[])
total = 0
for src in c.news_sources:
    items = scraper.fetch_source(src, max_items=5)
    print(f"{src['name']}: 抓取 {len(items)} 条")
    for item in items[:3]:
        print(f"   - {item.original_title[:70]}")
    total += len(items)
print(f"\n总计: {total} 条")

# 测试正文抓取
if total > 0:
    for src in c.news_sources:
        items = scraper.fetch_source(src, max_items=1)
        if items:
            content = scraper.fetch_article_content(items[0].url, max_chars=500)
            print(f"\n[{items[0].source}] 正文预览 ({len(content)} 字):")
            print(content[:300])
            break
