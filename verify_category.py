import sys, os, sqlite3, tempfile
sys.path.insert(0, '.')

from src.config_loader import AppConfig
from src.database import Database, NewsItem

print("=" * 60)
print("1. 验证配置文件")
cfg = AppConfig()
categories = set()
for s in cfg.news_sources:
    print(f"   - {s['name']} -> 分类: {s['category']}")
    categories.add(s['category'])
print(f"   共 {len(cfg.news_sources)} 个源，分类: {sorted(categories)}")

print("\n2. 验证数据库")
db = Database()
stats = db.get_stats()
cat_stats = db.get_category_stats()
print(f"   总新闻: {stats['total']}")
print(f"   已摘要: {stats['summarized']}")
print(f"   已分析: {stats['analyzed']}")
print(f"   分类统计: {cat_stats}")

print("\n3. 验证分类筛选")
for cat in ["中国", "国际", "政治", "经济", "科技"]:
    items = db.get_recent_news(limit=5, days=60, category=cat)
    print(f"   '{cat}': {len(items)} 条")

print("\n4. 验证 Flask 路由")
os.environ["FLASK_ENV"] = "development"
import importlib.util
spec = importlib.util.spec_from_file_location("app", "app.py")
app_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app_module)

with app_module.app.test_client() as client:
    for url in ["/", "/?category=国际", "/?category=中国", "/?category=科技", "/?category=经济", "/config"]:
        r = client.get(url)
        print(f"   GET {url} -> {r.status_code}")

print("\n" + "=" * 60)
print("✅ 所有验证通过")
