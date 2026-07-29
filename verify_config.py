import sys
sys.path.insert(0, ".")
from src.config_loader import AppConfig

c = AppConfig()
print(f"新闻源总数: {len(c.news_sources)}")
for s in c.news_sources:
    print(f"  - {s['name']}: {s['url']}")
print(f"关键词: {c.keywords}")
print(f"LLM: {c.llm_provider} / {c.llm_model}")
print("OK - 配置文件解析成功")
