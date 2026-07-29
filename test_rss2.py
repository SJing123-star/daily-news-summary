import feedparser, requests
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"}
urls = [
    ("BBC中文", "https://www.bbc.com/zhongwen/simp/index.xml"),
    ("Reuters", "https://feeds.reuters.com/Reuters/worldNews"),
    ("联合早报", "https://www.zaobao.com/news/realtime.xml"),
    ("新华网时政", "http://www.news.cn/rss/2018news.xml"),
]
for name, url in urls:
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        print(f"{name}: HTTP {resp.status_code}, len={len(resp.content)}")
        r = feedparser.parse(resp.content)
        print(f"  feedparser entries: {len(r.entries)}")
        if r.entries:
            print(f"  示例: {(r.entries[0].get('title') or '')[:60]}")
    except Exception as e:
        print(f"{name}: 失败 - {e}")
