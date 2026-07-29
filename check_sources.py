# -*- coding: utf-8 -*-
import sqlite3
conn = sqlite3.connect('news.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# 查询所有新闻来源分布
cursor.execute('SELECT source, category, COUNT(*) as cnt FROM news GROUP BY source, category ORDER BY cnt DESC')
rows = cursor.fetchall()

print('=' * 70)
print('新闻来源分布')
print('=' * 70)

for row in rows:
    print(f'{row["source"]:30} | {row["category"]:10} | {row["cnt"]} 条')

# 检查是否有网络安全源的新闻
cursor.execute('SELECT id, title, source, category FROM news WHERE source LIKE "%SANS%" OR source LIKE "%Security%" OR source LIKE "%CISA%"')
rows = cursor.fetchall()

print(f'\n{"=" * 70}')
print(f'网络安全源相关新闻 (共 {len(rows)} 条)')
print('=' * 70)

for row in rows:
    print(f'{row["id"]:4} | {row["category"]:10} | {row["source"]:20} | {row["title"][:50]}...')

conn.close()