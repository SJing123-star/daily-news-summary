import sys
sys.path.insert(0, '.')

from src.config_loader import AppConfig
from src.llm_client import LLMClient

cfg = AppConfig()
llm = LLMClient(
    provider=cfg.llm_provider,
    api_key=cfg.llm_api_key,
    model=cfg.llm_model,
    base_url=cfg.llm_base_url,
)

test_news = {
    "source": "纽约时报",
    "title": "China's import of custard apples is sparking fears in Taiwan",
    "summary": "Taiwan's agriculture ministry is worried that Beijing could use its growing import of custard apples to exert political pressure on the island.",
    "content": "Taiwan's agriculture ministry has raised concerns about China's growing import of custard apples, warning that Beijing could use the trade as a political tool.",
}

title, summary = llm.generate_summary(
    test_news['title'],
    test_news['summary'],
    test_news['content'],
    test_news['source'],
)

print("生成标题:", title)
print("生成摘要:", summary)
print("长度:", len(summary), "字")
