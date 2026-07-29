import sys
sys.path.insert(0, '.')

from src.parallel_analyzer import ParallelNewsAnalyzer, PipelineConfig

print("测试并行分析器抓取 Al Jazeera...")

analyzer = ParallelNewsAnalyzer()

# 测试只抓取 Al Jazeera
aljazeera_source = None
for src in analyzer.config.news_sources:
    if 'Al Jazeera' in src.get('name', ''):
        aljazeera_source = src
        break

if not aljazeera_source:
    print("❌ 未找到 Al Jazeera 配置")
    sys.exit(1)

print(f"\n📡 测试源: {aljazeera_source['name']}")
print(f"🔗 URL: {aljazeera_source['url']}")
print(f"✅ enabled: {aljazeera_source.get('enabled', True)}")

# 直接使用 scraper 测试
print("\n🔄 测试直接抓取...")
items = analyzer.scraper.fetch_source(aljazeera_source, max_items=5)
print(f"获取到 {len(items)} 条新闻")
for i, item in enumerate(items):
    print(f"  {i+1}. {item.original_title[:60]}...")

# 检查所有源列表
print("\n📋 所有新闻源列表:")
for i, src in enumerate(analyzer.config.news_sources):
    enabled = src.get('enabled', True)
    status = '✅' if enabled else '❌'
    print(f"  {status} [{i+1}] {src['name']} - enabled={enabled}")