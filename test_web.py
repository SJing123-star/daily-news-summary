import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import app

client = app.test_client()

print("=== 测试首页 ===")
resp = client.get("/")
print(f"状态码: {resp.status_code}")
html = resp.get_data(as_text=True)
print(f"HTML 长度: {len(html)} 字")
assert "news-card" in html or "news" in html.lower(), "新闻卡片未在 HTML 中"
print("[OK] 首页正常")

print("\n=== 测试 /config ===")
resp = client.get("/config")
print(f"状态码: {resp.status_code}")
data = resp.get_json()
print(f"返回 JSON keys: {list(data.keys())}")
print(f"新闻源: {len(data.get('news_sources', []))} 个")
print(f"LLM: {data.get('llm_provider')}/{data.get('llm_model')}")
print("[OK] 配置接口正常")

print("\n=== 测试 POST /api/collect ===")
resp = client.post("/api/collect")
print(f"状态码: {resp.status_code}")
data = resp.get_json()
print(f"结果: {data}")
print("[OK] 抓取接口正常")

print("\n=== 测试新闻详情页 ===")
from src.database import Database
db = Database()
news = db.get_recent_news(limit=3)
for n in news:
    resp = client.get(f"/news/{n.id}")
    print(f"  /news/{n.id} - 状态码 {resp.status_code}, 标题: {n.title[:50]}")
assert resp.status_code == 200, "详情页非 200"
print("[OK] 详情页正常")

print("\n=== 测试分析接口 ===")
if news:
    resp = client.post(f"/api/analyze/{news[0].id}")
    print(f"POST /api/analyze/{news[0].id} - 状态码 {resp.status_code}")
    data = resp.get_json()
    print(f"分析结果 keys: {list(data.keys()) if data else None}")
    print(f"简报: {(data.get('brief', '') or '')[:100]}")

print("\n====== Web 测试全部通过 ======")
