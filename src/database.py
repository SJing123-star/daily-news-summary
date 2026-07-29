import os
import sqlite3
import time
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Any

logger = logging.getLogger(__name__)

try:
    import jieba
    HAS_JIEBA = True
except ImportError:
    HAS_JIEBA = False

# 导入加密模块
try:
    from .crypto import encrypt, decrypt
    HAS_CRYPTO = True
except ImportError:
    # 如果加密模块不可用，使用简单的占位函数
    encrypt = lambda x: x
    decrypt = lambda x: x
    HAS_CRYPTO = False

try:
    from .utils import clean_text
except ImportError:
    # 如果工具模块不可用，使用本地实现
    import re
    def clean_text(text: str) -> str:
        if not text:
            return ""
        text = text.lower().strip()
        text = re.sub(r'[^\w\s\u4e00-\u9fff]', '', text)
        text = re.sub(r'\s+', ' ', text)
        return text


@dataclass
class NewsItem:
    url: str
    original_title: str
    source: str
    category: str = ""
    publish_time: str = ""
    content: str = ""
    title: str = ""
    one_line_summary: str = ""
    analysis_brief: str = ""
    is_summary_done: int = 0
    is_analysis_done: int = 0
    is_highlighted: int = 0
    is_strategy_matched: int = 0
    id: Optional[int] = None
    created_at: str = ""


@dataclass
class LLMConfig:
    name: str
    provider: str
    model: str
    base_url: str = ""
    api_key: str = ""
    max_tokens: int = 2000
    timeout: int = 60
    temperature: float = 0.7
    is_active: int = 0
    last_test_time: str = ""
    health_status: str = "unknown"
    avg_response_time: float = 0.0
    id: Optional[int] = None
    created_at: str = ""
    updated_at: str = ""


class Database:
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "news.db"
            )
        self.db_path = db_path
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS news (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT UNIQUE NOT NULL,
                    original_title TEXT NOT NULL,
                    title TEXT,
                    source TEXT,
                    category TEXT,
                    publish_time TEXT,
                    content TEXT,
                    one_line_summary TEXT,
                    analysis_brief TEXT,
                    is_summary_done INTEGER DEFAULT 0,
                    is_analysis_done INTEGER DEFAULT 0,
                    is_highlighted INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            try:
                conn.execute("ALTER TABLE news ADD COLUMN is_highlighted INTEGER DEFAULT 0")
            except sqlite3.OperationalError:
                pass
            try:
                conn.execute("ALTER TABLE news ADD COLUMN is_strategy_matched INTEGER DEFAULT 0")
            except sqlite3.OperationalError:
                pass
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_news_publish_time ON news(publish_time)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_news_source ON news(source)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_news_category ON news(category)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_news_matched ON news(is_strategy_matched, is_highlighted)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_news_summary_done ON news(is_summary_done)
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS llm_configs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    base_url TEXT,
                    api_key TEXT,
                    max_tokens INTEGER DEFAULT 2000,
                    timeout INTEGER DEFAULT 60,
                    temperature REAL DEFAULT 0.7,
                    is_active INTEGER DEFAULT 0,
                    last_test_time TEXT,
                    health_status TEXT DEFAULT 'unknown',
                    avg_response_time REAL DEFAULT 0.0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def exists_by_url(self, url: str) -> bool:
        with self._get_conn() as conn:
            row = conn.execute("SELECT id FROM news WHERE url = ?", (url,)).fetchone()
            return row is not None

    def is_duplicate(self, title: str, url: str = "", summary: str = "", threshold: float = 0.8) -> bool:
        """
        检测新闻是否重复（优化版）
        
        优化措施：
        1. URL精确匹配优先
        2. 只检查最近7天的新闻（时间范围限制）
        3. 限制比较记录数为最近100条
        """
        if self.exists_by_url(url):
            return True

        title_clean = self._clean_text(title)
        if not title_clean:
            return False

        with self._get_conn() as conn:
            # 只检查最近7天的新闻，大幅减少比较数量
            rows = conn.execute("""
                SELECT original_title, one_line_summary
                FROM news
                WHERE original_title IS NOT NULL AND original_title != ''
                  AND publish_time > datetime('now', '-7 days')
                ORDER BY id DESC
                LIMIT 100
            """).fetchall()

            for row in rows:
                existing_title = self._clean_text(row["original_title"] or "")
                if not existing_title:
                    continue

                title_sim = self._calculate_similarity(title_clean, existing_title)
                if title_sim >= threshold:
                    return True

                if summary:
                    existing_summary = self._clean_text(row["one_line_summary"] or "")
                    if existing_summary:
                        summary_sim = self._calculate_similarity(
                            self._clean_text(summary),
                            existing_summary
                        )
                        if summary_sim >= threshold:
                            return True

        return False

    @staticmethod
    def _clean_text(text: str) -> str:
        """清理文本（委托给工具模块）"""
        return clean_text(text)

    @staticmethod
    def _tokenize(text: str) -> list:
        if not text:
            return []
        if HAS_JIEBA:
            return jieba.lcut(text)
        return text.split()

    @staticmethod
    def _calculate_similarity(text1: str, text2: str) -> float:
        if not text1 or not text2:
            return 0.0
        
        words1 = set(Database._tokenize(text1))
        words2 = set(Database._tokenize(text2))
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1 & words2
        union = words1 | words2
        
        if not union:
            return 0.0
        
        return len(intersection) / len(union)

    def save_news(self, item: NewsItem) -> int:
        """保存新闻（带异常处理）"""
        try:
            with self._get_conn() as conn:
                if item.id:
                    conn.execute("""
                        UPDATE news SET
                            url=?, original_title=?, title=?, source=?, category=?,
                            publish_time=?, content=?, one_line_summary=?,
                            analysis_brief=?, is_summary_done=?, is_analysis_done=?,
                            is_highlighted=?, is_strategy_matched=?
                        WHERE id=?
                    """, (
                        item.url, item.original_title, item.title, item.source,
                        item.category, item.publish_time, item.content,
                        item.one_line_summary, item.analysis_brief,
                        item.is_summary_done, item.is_analysis_done,
                        item.is_highlighted, item.is_strategy_matched, item.id
                    ))
                    conn.commit()
                    return item.id
                else:
                    cur = conn.execute("""
                        INSERT INTO news
                        (url, original_title, title, source, category, publish_time,
                         content, one_line_summary, analysis_brief,
                         is_summary_done, is_analysis_done, is_highlighted, is_strategy_matched)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        item.url, item.original_title, item.title, item.source,
                        item.category, item.publish_time, item.content,
                        item.one_line_summary, item.analysis_brief,
                        item.is_summary_done, item.is_analysis_done,
                        item.is_highlighted, item.is_strategy_matched
                    ))
                    conn.commit()
                    return cur.lastrowid
        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint failed" in str(e):
                logger.warning(f"新闻URL已存在，跳过重复: {item.url}")
                return -1
            logger.error(f"保存新闻失败（完整性错误）: {e}")
            raise
        except sqlite3.Error as e:
            logger.error(f"保存新闻失败（数据库错误）: {e}, URL: {item.url}")
            raise
        except Exception as e:
            logger.error(f"保存新闻失败（未知错误）: {e}, URL: {item.url}")
            raise

    def update_summary(self, news_id: int, one_line_summary: str, title: str = ""):
        with self._get_conn() as conn:
            conn.execute("""
                UPDATE news SET one_line_summary=?, title=?, is_summary_done=1
                WHERE id=?
            """, (one_line_summary, title or one_line_summary, news_id))
            conn.commit()

    def update_analysis(self, news_id: int, analysis_brief: str):
        with self._get_conn() as conn:
            conn.execute("""
                UPDATE news SET analysis_brief=?, is_analysis_done=1 WHERE id=?
            """, (analysis_brief, news_id))
            conn.commit()

    def get_news_by_id(self, news_id: int) -> Optional[NewsItem]:
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM news WHERE id=?", (news_id,)).fetchone()
            return self._row_to_item(row) if row else None

    def get_recent_news(self, limit: int = 50, days: int = 30, category: str = None, offset: int = 0) -> List[NewsItem]:
        with self._get_conn() as conn:
            if category and category.lower() != "all":
                rows = conn.execute("""
                    SELECT * FROM news
                    WHERE category = ?
                      AND (publish_time >= datetime('now', ?)
                           OR publish_time IS NULL OR publish_time = '')
                    ORDER BY
                        CASE 
                            WHEN publish_time >= datetime('now', '-2 days') 
                                 AND (is_strategy_matched = 1 OR is_highlighted = 1) THEN 0
                            ELSE 1 
                        END,
                        publish_time DESC,
                        id DESC
                    LIMIT ? OFFSET ?
                """, (category, f"-{days} days", limit, offset)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT * FROM news
                    WHERE publish_time >= datetime('now', ?)
                       OR publish_time IS NULL OR publish_time = ''
                    ORDER BY
                        CASE 
                            WHEN publish_time >= datetime('now', '-2 days') 
                                 AND (is_strategy_matched = 1 OR is_highlighted = 1) THEN 0
                            ELSE 1 
                        END,
                        publish_time DESC,
                        id DESC
                    LIMIT ? OFFSET ?
                """, (f"-{days} days", limit, offset)).fetchall()
            return [self._row_to_item(r) for r in rows]

    def get_news_count(self, category: str = None) -> int:
        with self._get_conn() as conn:
            if category and category.lower() != "all":
                row = conn.execute("""
                    SELECT COUNT(*) as c FROM news
                    WHERE category = ?
                      AND (publish_time >= datetime('now', '-3650 days')
                           OR publish_time IS NULL OR publish_time = '')
                """, (category,)).fetchone()
            else:
                row = conn.execute("""
                    SELECT COUNT(*) as c FROM news
                    WHERE publish_time >= datetime('now', '-3650 days')
                       OR publish_time IS NULL OR publish_time = ''
                """).fetchone()
            return row["c"] if row else 0

    def get_matched_news(self, limit: int = 50, offset: int = 0) -> List[NewsItem]:
        with self._get_conn() as conn:
            rows = conn.execute("""
                SELECT * FROM news
                WHERE (is_strategy_matched = 1 OR is_highlighted = 1)
                  AND (publish_time >= datetime('now', '-3650 days')
                       OR publish_time IS NULL OR publish_time = '')
                ORDER BY
                    CASE 
                        WHEN publish_time >= datetime('now', '-2 days') 
                             AND (is_strategy_matched = 1 OR is_highlighted = 1) THEN 0
                        ELSE 1 
                    END,
                    publish_time DESC,
                    id DESC
                LIMIT ? OFFSET ?
            """, (limit, offset)).fetchall()
            return [self._row_to_item(r) for r in rows]

    def get_matched_news_count(self) -> int:
        with self._get_conn() as conn:
            row = conn.execute("""
                SELECT COUNT(*) as c FROM news
                WHERE (is_strategy_matched = 1 OR is_highlighted = 1)
                  AND (publish_time >= datetime('now', '-3650 days')
                       OR publish_time IS NULL OR publish_time = '')
            """).fetchone()
            return row["c"] if row else 0

    def get_news_by_date_range(self, start_date: str, end_date: str, category: str = None, limit: int = 200) -> List[NewsItem]:
        with self._get_conn() as conn:
            query = """
                SELECT * FROM news
                WHERE publish_time >= ? AND publish_time <= ?
            """
            params = [f"{start_date} 00:00:00", f"{end_date} 23:59:59"]
            
            if category and category.lower() != "all":
                query += " AND category = ?"
                params.append(category)
            
            query += """
                ORDER BY
                    is_highlighted DESC,
                    publish_time DESC,
                    id DESC
                LIMIT ?
            """
            params.append(limit)
            
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_item(r) for r in rows]

    def get_pending_summary(self, limit: int = 20) -> List[NewsItem]:
        with self._get_conn() as conn:
            rows = conn.execute("""
                SELECT * FROM news WHERE is_summary_done = 0
                ORDER BY id DESC LIMIT ?
            """, (limit,)).fetchall()
            return [self._row_to_item(r) for r in rows]

    def get_stats(self) -> dict:
        with self._get_conn() as conn:
            total = conn.execute("SELECT COUNT(*) as c FROM news").fetchone()["c"]
            summarized = conn.execute(
                "SELECT COUNT(*) as c FROM news WHERE is_summary_done=1"
            ).fetchone()["c"]
            analyzed = conn.execute(
                "SELECT COUNT(*) as c FROM news WHERE is_analysis_done=1"
            ).fetchone()["c"]
            return {
                "total": total,
                "summarized": summarized,
                "analyzed": analyzed,
                "pending_summary": total - summarized,
                "pending_analysis": total - analyzed,
            }

    def get_category_stats(self) -> List[dict]:
        with self._get_conn() as conn:
            rows = conn.execute("""
                SELECT category, COUNT(*) as count
                FROM news
                GROUP BY category
                ORDER BY count DESC
            """).fetchall()
            return [
                {"category": r["category"] or "未分类", "count": r["count"]}
                for r in rows
            ]

    def cleanup_old(self, days: int = 30):
        with self._get_conn() as conn:
            conn.execute("""
                DELETE FROM news
                WHERE id IN (
                    SELECT id FROM news
                    WHERE (publish_time IS NULL OR publish_time = ''
                           OR publish_time < datetime('now', ?))
                    ORDER BY id ASC
                )
            """, (f"-{days} days",))
            conn.commit()

    def get_all_llm_configs(self) -> List[LLMConfig]:
        with self._get_conn() as conn:
            rows = conn.execute("SELECT * FROM llm_configs ORDER BY id DESC").fetchall()
            return [self._row_to_llm_config(r) for r in rows]

    def get_llm_config_by_id(self, config_id: int) -> Optional[LLMConfig]:
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM llm_configs WHERE id = ?", (config_id,)).fetchone()
            return self._row_to_llm_config(row) if row else None

    def get_active_llm_config(self) -> Optional[LLMConfig]:
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM llm_configs WHERE is_active = 1 LIMIT 1").fetchone()
            return self._row_to_llm_config(row) if row else None

    def add_llm_config(self, config: LLMConfig) -> int:
        with self._get_conn() as conn:
            cursor = conn.execute("""
                INSERT INTO llm_configs (name, provider, model, base_url, api_key, max_tokens, timeout, temperature, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                config.name, config.provider, config.model, config.base_url,
                encrypt(config.api_key), config.max_tokens, config.timeout, config.temperature,
                config.is_active
            ))
            conn.commit()
            return cursor.lastrowid

    def update_llm_config(self, config_id: int, **kwargs) -> bool:
        if not kwargs:
            return False
        
        # 加密api_key（如果存在）
        if "api_key" in kwargs:
            kwargs["api_key"] = encrypt(kwargs["api_key"])
        
        # 分离需要绑定参数的字段和SQL字面量
        bind_fields = []
        values = []
        for k, v in kwargs.items():
            bind_fields.append(f"{k} = ?")
            values.append(v)
        
        # 在SQL中直接使用CURRENT_TIMESTAMP（作为SQL函数，不是字符串）
        fields = ", ".join(bind_fields) + ", updated_at = CURRENT_TIMESTAMP"
        values.append(config_id)
        
        with self._get_conn() as conn:
            cursor = conn.execute(f"UPDATE llm_configs SET {fields} WHERE id = ?", values)
            conn.commit()
            return cursor.rowcount > 0

    def delete_llm_config(self, config_id: int) -> bool:
        with self._get_conn() as conn:
            cursor = conn.execute("DELETE FROM llm_configs WHERE id = ?", (config_id,))
            conn.commit()
            return cursor.rowcount > 0

    def set_active_llm(self, config_id: int) -> bool:
        with self._get_conn() as conn:
            conn.execute("UPDATE llm_configs SET is_active = 0")
            cursor = conn.execute("UPDATE llm_configs SET is_active = 1 WHERE id = ?", (config_id,))
            conn.commit()
            return cursor.rowcount > 0

    def update_news_highlight(self, news_id: int, is_highlighted: int):
        with self._get_conn() as conn:
            conn.execute("""
                UPDATE news
                SET is_highlighted = ?
                WHERE id = ?
            """, (is_highlighted, news_id))
            conn.commit()

    def update_news_highlight_batch(self, updates: list):
        if not updates:
            return
        with self._get_conn() as conn:
            conn.executemany("""
                UPDATE news
                SET is_highlighted = ?
                WHERE id = ?
            """, updates)
            conn.commit()

    def update_news_strategy_matched_batch(self, updates: list):
        if not updates:
            return
        with self._get_conn() as conn:
            conn.executemany("""
                UPDATE news
                SET is_strategy_matched = ?
                WHERE id = ?
            """, updates)
            conn.commit()

    def update_llm_health(self, config_id: int, health_status: str, avg_response_time: float):
        with self._get_conn() as conn:
            conn.execute("""
                UPDATE llm_configs
                SET health_status = ?, avg_response_time = ?, last_test_time = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (health_status, avg_response_time, config_id))
            conn.commit()

    @staticmethod
    def _row_to_llm_config(row: Any) -> LLMConfig:
        return LLMConfig(
            id=row["id"],
            name=row["name"],
            provider=row["provider"],
            model=row["model"],
            base_url=row["base_url"] or "",
            api_key=decrypt(row["api_key"] or ""),  # 解密API密钥
            max_tokens=row["max_tokens"] or 2000,
            timeout=row["timeout"] or 60,
            temperature=row["temperature"] or 0.7,
            is_active=row["is_active"] or 0,
            last_test_time=row["last_test_time"] or "",
            health_status=row["health_status"] or "unknown",
            avg_response_time=row["avg_response_time"] or 0.0,
            created_at=row["created_at"] or "",
            updated_at=row["updated_at"] or "",
        )

    @staticmethod
    def _row_to_item(row: Any) -> NewsItem:
        return NewsItem(
            id=row["id"],
            url=row["url"],
            original_title=row["original_title"],
            title=row["title"] or row["original_title"],
            source=row["source"] or "",
            category=row["category"] or "",
            publish_time=row["publish_time"] or "",
            content=row["content"] or "",
            one_line_summary=row["one_line_summary"] or "",
            analysis_brief=row["analysis_brief"] or "",
            is_summary_done=row["is_summary_done"] or 0,
            is_analysis_done=row["is_analysis_done"] or 0,
            is_highlighted=row["is_highlighted"] if "is_highlighted" in row.keys() else 0,
            is_strategy_matched=row["is_strategy_matched"] if "is_strategy_matched" in row.keys() else 0,
            created_at=row["created_at"] or "",
        )
