import sys
sys.path.insert(0, '.')

from src.config_loader import AppConfig
from src.scraper import Scraper

cfg = AppConfig()
scraper = Scraper(min_title_length=cfg.min_title_length, keywords=cfg.keywords)

src = {"name": "ms观察", "type": "html", "url": "https://msguancha.com/plus/list.php?tid=10", "category": "政治", "link_selector": "a[href*='/a/lanmu26']"}

items = scraper.fetch_source(src, max_items=5)

print(f"抓取结果: {len(items)} 条")
for it in items:
    print(f"  - [{it.publish_time}] {it.title}")
    print(f"    URL: {it.url}")
    print()
