# -*- coding: utf-8 -*-
import sqlite3
conn = sqlite3.connect('news.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute('SELECT id, title, source, category, publish_time, is_summary_done, is_highlighted FROM news WHERE category = ? ORDER BY publish_time DESC', ('网络安全',))
rows = cursor.fetchall()

print('=' * 70)
print(f'网络安全新闻查询结果 (共 {len(rows)} 条)')
print('=' * 70)

for i, row in enumerate(rows, 1):
    pub_time = row['publish_time'].strftime('%Y-%m-%d %H:%M') if row['publish_time'] else '未知'
    summary = '✓' if row['is_summary_done'] else '○'
    highlight = '★' if row['is_highlighted'] else ''
    print(f'\n{i}. {row["title"]}')
    print(f'   来源: {row["source"]} | 分类: {row["category"]}')
    print(f'   时间: {pub_time} | 摘要: {summary} | 高亮: {highlight}')

conn.close()