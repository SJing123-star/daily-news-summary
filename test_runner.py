import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config_loader import AppConfig
from src.database import Database, NewsItem
from src.scraper import Scraper
from src.llm_client import LLMClient
from src.analyzer import NewsAnalyzer

print("[OK] 所有模块导入成功")

c = AppConfig()
print(f"[OK] 配置加载: {len(c.news_sources)} 个新闻源, {len(c.keywords)} 个关键词")
for s in c.news_sources:
    print(f"     - {s.get('name')} ({s.get('type')}): {s.get('url')}")

db = Database()
stats = db.get_stats()
print(f"[OK] 数据库初始化: {stats['total']} 条记录")

scraper = Scraper(min_title_length=c.min_title_length, keywords=c.keywords)
print(f"[OK] Scraper 初始化完成")

llm = LLMClient(provider=c.llm_provider, api_key=c.llm_api_key, model=c.llm_model)
print(f"[OK] LLM 初始化: {c.llm_provider}/{c.llm_model} (API Key 已{'配置' if c.llm_api_key else '未配置'})")

analyzer = NewsAnalyzer(config=c)
print(f"[OK] NewsAnalyzer 初始化完成")

print("\n=== 快速 RSS 测试 (抓取第一个新闻源的 3 条) ===")
first = c.news_sources[0]
try:
    items = scraper.fetch_source(first, max_items=3)
    print(f"[OK] 从 {first['name']} 抓取到 {len(items)} 条")
    for item in items[:2]:
        print(f"     - {item.original_title[:60]}...")
except Exception as e:
    print(f"[WARN] RSS 抓取失败: {e}")

print("\n=== 数据库 CRUD 测试 ===")
test_item = NewsItem(
    url="http://test.com/example-12345",
    original_title="测试新闻标题 - 来自测试",
    title="AI 生成的中文摘要",
    source="测试源",
    category="国际",
    publish_time="2024-06-22 10:00:00",
    content="这是一条测试新闻的正文内容。",
    one_line_summary="这是一条测试的一句话摘要，用于验证数据库 CRUD 功能。",
    analysis_brief="",
    is_summary_done=1,
    is_analysis_done=0,
)
news_id = db.save_news(test_item)
print(f"[OK] 保存测试新闻，ID={news_id}")

fetched = db.get_news_by_id(news_id)
print(f"[OK] 读取测试: {fetched.title if fetched else '未找到'}")

news_list = db.get_recent_news(limit=10)
print(f"[OK] get_recent_news 返回 {len(news_list)} 条")

# 测试去重
assert db.exists_by_url("http://test.com/example-12345"), "URL 去重失效"
print("[OK] URL 去重功能正常")

# 清理测试数据
with db._get_conn() as conn:
    conn.execute("DELETE FROM news WHERE url LIKE 'http://test.com/%'")
    conn.commit()
print("[OK] 清理测试数据")

print("\n=== Flask 路由测试 ===")
try:
    from app import app
    with app.test_client() as client:
        resp = client.get("/")
        print(f"[OK] GET / 返回状态码 {resp.status_code}")
        resp = client.get("/config")
        print(f"[OK] GET /config 返回状态码 {resp.status_code}")
        resp = client.post("/api/collect")
        print(f"[OK] POST /api/collect 返回状态码 {resp.status_code}")
except Exception as e:
    print(f"[WARN] Flask 路由测试有问题: {e}")

print("\n====== 所有测试完成 ======")
