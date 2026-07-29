# -*- coding: utf-8 -*-
import requests

sources = [
    ('SANS研究所', 'https://www.sans.org/rss/'),
    ('SecurityFocus', 'https://www.securityfocus.com/rss'),
    ('CERT-CISA', 'https://www.cisa.gov/cybersecurity-advisories/all.xml'),
]

print('=' * 70)
print('测试网络安全RSS源')
print('=' * 70)

for name, url in sources:
    try:
        resp = requests.get(url, timeout=10)
        print(f'\n{name}: {url}')
        print(f'状态码: {resp.status_code}')
        print(f'内容长度: {len(resp.text)} 字符')
        if resp.status_code == 200:
            # 检查是否是RSS/XML格式
            content = resp.text[:500]
            print(f'前500字符:\n{content}')
    except Exception as e:
        print(f'\n{name}: {url}')
        print(f'错误: {e}')