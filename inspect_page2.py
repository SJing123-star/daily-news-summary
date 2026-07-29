import sys
sys.path.insert(0, '.')

import requests
from bs4 import BeautifulSoup

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

resp = requests.get("https://msguancha.com/plus/list.php?tid=10", headers=headers, timeout=15)
resp.encoding = "utf-8"
soup = BeautifulSoup(resp.text, "lxml")

# 找主内容区域
print("=== 找主内容容器 ===")
for sel in ["#list", ".list", ".news-list", ".article-list", "main", "article"]:
    el = soup.select_one(sel)
    if el:
        print(f"  找到 {sel}: {el.get_text(strip=True)[:50]}")

# 找包含 /a/lanmu26 的链接的父容器
print("\n=== 找 lanmu26 链接的上下文 ===")
lanmu_links = soup.select("a[href*='/a/lanmu26']")
print(f"lanmu26 链接总数: {len(lanmu_links)}")
if lanmu_links:
    first = lanmu_links[0]
    parent = first.parent
    grandparent = parent.parent if parent else None
    print(f"第一个链接文字: {first.get_text(strip=True)[:60]}")
    print(f"父元素: <{parent.name}> class={parent.get('class')} id={parent.get('id')}")
    if grandparent:
        print(f"祖父元素: <{grandparent.name}> class={grandparent.get('class')} id={grandparent.get('id')}")

# 打印包含 lanmu26 的行
print("\n=== 所有 /a/lanmu26 链接 (前10个) ===")
for a in lanmu_links[:10]:
    parent = a.parent
    grandparent = parent.parent if parent else None
    print(f"  [{parent.name}]{grandparent.name if grandparent else ''}: {a.get_text(strip=True)[:50]} | href={a.get('href')}")

# 找日期元素
print("\n=== 找日期模式 ===")
dates = soup.select("span.time, .time, .date, [class*='date'], [class*='time']")
for d in dates[:10]:
    print(f"  <{d.name}> {d.get('class')}: {d.get_text(strip=True)[:30]}")
