import sqlite3, os
db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "news.db")
if os.path.exists(db_path):
    try:
        conn = sqlite3.connect(db_path)
        conn.execute("DELETE FROM news")
        conn.commit()
        count = conn.execute("SELECT COUNT(*) FROM news").fetchone()[0]
        print(f"数据库已清理，剩余 {count} 条新闻")
        conn.close()
    except Exception as e:
        print(f"清理失败: {e}")
        print("尝试直接删除文件...")
        try:
            os.remove(db_path)
            print("文件已删除，下次启动会自动重建")
        except Exception as e2:
            print(f"删除也失败: {e2}")
else:
    print("数据库不存在，无需清理")
