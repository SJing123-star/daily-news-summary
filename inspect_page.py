import sys
sys.path.insert(0, '.')

import requests
from bs4 import BeautifulSoup

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

resp = requests.get("https://msguancha.com/plus/list.php?tid=10", headers=headers, timeout=15)
resp.encoding = "utf-8"
print(f"状态码: {resp.status_code}")
print(f"编码: {resp.apparent_encoding}")
print(f"内容长度: {len(resp.text)}")

soup = BeautifulSoup(resp.text, "lxml")

# 查找所有链接
print("\n=== 查找页面中的链接结构 ===")
links = soup.find_all("a")[:30]
for a in links:
    href = a.get("href", "")
    text = a.get_text(strip=True)
    if href and text and len(text) > 5:
        print(f"  href={href[:80]} | text={text[:60]}")

print("\n=== 查看主要容器结构 ===")
main = soup.select_one("body")
if main:
    # 找包含链接的列表项
    list_items = soup.select("ul li, .list-item, .item, .news-item, tr")
    print(f"列表容器数量: {len(list_items)}")
    if list_items:
        for item in list_items[:3]:
            print(f"  <{item.name}>: {item.get_text(strip=True)[:80]}")
