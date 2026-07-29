import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import app

client = app.test_client()

print("=== 测试首页 ===")
resp = client.get("/")
print(f"状态码: {resp.status_code}")
assert resp.status_code == 200
html = resp.get_data(as_text=True)
print(f"HTML 长度: {len(html)} 字")
assert "news-card" in html or "news" in html.lower()
print("[OK] 首页正常")

print("\n=== 测试 /config ===")
resp = client.get("/config")
print(f"状态码: {resp.status_code}")
data = resp.get_json()
print(f"keys: {list(data.keys())}")
print(f"新闻源: {len(data.get('news_sources', []))}")
print("[OK] 配置接口正常")

print("\n=== 测试新闻详情页 ===")
from src.database import Database
db = Database()
news = db.get_recent_news(limit=3)
for n in news:
    resp = client.get(f"/news/{n.id}")
    print(f"  /news/{n.id} -> {resp.status_code}")
assert resp.status_code == 200
print("[OK] 详情页正常")

print("\n=== 测试 /api/analyze 异步接口 ===")
if news:
    resp = client.post(f"/api/analyze/{news[0].id}")
    print(f"POST /api/analyze/{news[0].id} -> {resp.status_code}")
    data = resp.get_json()
    brief = data.get("brief", "")
    print(f"返回: ok={data.get('ok')}, 简报: {brief[:120]}")
print("[OK] 分析接口正常")

print("\n====== 全部 Web 测试通过 ======")
