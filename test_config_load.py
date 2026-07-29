import sys
sys.path.insert(0, '.')

from src.config_loader import AppConfig

config = AppConfig()

print(f"📋 加载的配置文件: {config.config_path}")
print(f"\n📡 新闻源数量: {len(config.news_sources)}")
print("\n所有新闻源:")
for i, src in enumerate(config.news_sources):
    name = src.get('name', '未知')
    enabled = src.get('enabled', True)
    status = '✅' if enabled else '❌'
    print(f"  {status} [{i+1}] {name}")

print("\n🔍 搜索 Al Jazeera:")
found = False
for src in config.news_sources:
    if 'Al' in src.get('name', '') or 'Jazeera' in src.get('name', ''):
        print(f"  找到: {src}")
        found = True

if not found:
    print("  未找到！")
    print("\n🔍 检查配置文件内容:")
    import os
    config_path = config.config_path
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = content.split('\n')
            for i, line in enumerate(lines[:65]):
                print(f"{i+1:3d}: {line}")
    else:
        print(f"配置文件不存在: {config_path}")