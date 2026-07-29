import sys, os
sys.path.insert(0, '.')

print("=== 调试配置加载 ===")

# 1. 检查 .env 文件
project_root = os.path.dirname(os.path.abspath(__file__))
dotenv_path = os.path.join(project_root, ".env")
print(f"1. .env 路径: {dotenv_path}")
print(f"   文件存在: {os.path.exists(dotenv_path)}")

if os.path.exists(dotenv_path):
    with open(dotenv_path) as f:
        print(f"   内容: {f.read().strip()}")

# 2. 检查 load_dotenv
from dotenv import load_dotenv
result = load_dotenv(dotenv_path)
print(f"\n2. load_dotenv() 返回: {result}")
print(f"   DEEPSEEK_API_KEY in os.environ: {'DEEPSEEK_API_KEY' in os.environ}")
if 'DEEPSEEK_API_KEY' in os.environ:
    print(f"   os.environ['DEEPSEEK_API_KEY']: {os.environ['DEEPSEEK_API_KEY'][:8]}...")

# 3. 检查 AppConfig
from src.config_loader import AppConfig
cfg = AppConfig()
print(f"\n3. AppConfig:")
print(f"   llm_api_key: {cfg.llm_api_key[:8] if cfg.llm_api_key else '(空)'}...")
print(f"   llm_provider: {cfg.llm_provider}")
print(f"   llm_model: {cfg.llm_model}")
print(f"   llm_base_url: {cfg.llm_base_url}")
