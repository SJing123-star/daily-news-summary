import logging
import random
import re
import time
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from urllib.parse import urlparse
from urllib3 import PoolManager

import feedparser
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]


def _safe_headers() -> dict:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Connection": "keep-alive",
    }


def _parse_rfc_time(time_str: Any) -> str:
    if not time_str:
        return ""
    try:
        if hasattr(time_str, "tm_year"):
            dt = datetime.fromtimestamp(time.mktime(time_str), tz=timezone.utc)
        else:
            time_str = str(time_str).strip()
            for fmt in (
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%dT%H:%M:%S.%fZ",
                "%a, %d %b %Y %H:%M:%S %z",
                "%a, %d %b %Y %H:%M:%S %Z",
                "%Y-%m-%d %H:%M:%S",
                "%Y/%m/%d %H:%M:%S",
                "%Y-%m-%d",
            ):
                try:
                    dt = datetime.strptime(time_str, fmt)
                    break
                except ValueError:
                    continue
            else:
                return time_str[:19]
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ""


class RawNews:
    def __init__(
        self,
        url: str,
        original_title: str,
        source: str,
        category: str = "",
        publish_time: str = "",
        summary: str = "",
        content: str = "",
        is_highlighted: bool = False,
        strategy: str = "",
    ):
        self.url = url
        self.original_title = original_title
        self.source = source
        self.category = category
        self.strategy = strategy
        self.publish_time = publish_time
        self.summary = summary
        self.content = content
        self.is_highlighted = is_highlighted


class Scraper:
    def __init__(self, min_title_length: int = 8, keywords: List[str] = None):
        self.min_title_length = min_title_length
        self.keywords = keywords or []
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        """创建配置优化的Session，支持连接池复用"""
        session = requests.Session()
        
        # 设置默认headers
        session.headers.update(_safe_headers())
        
        # 配置连接池：提高并发性能，复用TCP连接
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10,      # 连接池大小（每个主机的连接数）
            pool_maxsize=20,          # 最大连接数
            max_retries=2,            # 重试次数
            pool_block=False,         # 连接池满时不阻塞
        )
        
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # 连接超时设置
        session.timeout = 15
        
        return session

    def fetch_source(self, source_cfg: Dict[str, Any], max_items: int = 10) -> List[RawNews]:
        name = source_cfg.get("name", "Unknown")
        stype = source_cfg.get("type", "rss").lower()
        url = source_cfg.get("url", "")
        category = source_cfg.get("category", "")
        source_max_items = source_cfg.get("max_items", max_items)

        logger.info(f"抓取: {name} ({stype}) -> {url} (max: {source_max_items})")

        if stype == "rss":
            items = self._fetch_rss(url, source_max_items)
        elif stype == "html":
            items = self._fetch_html(url, source_cfg, source_max_items)
        else:
            logger.warning(f"未知类型 {stype}")
            items = []

        strategy = source_cfg.get("strategy", "")
        for it in items:
            it.source = name
            it.category = category or it.category
            it.strategy = strategy

        filtered = [
            it for it in items
            if len(it.original_title) >= self.min_title_length
        ]

        logger.info(f"  {name}: 抓取 {len(items)} 条, 保留 {len(filtered)} 条")
        time.sleep(random.uniform(0.8, 1.8))
        return filtered

    def _fetch_rss(self, url: str, max_items: int) -> List[RawNews]:
        result: List[RawNews] = []
        try:
            resp = self.session.get(url, timeout=15)
            resp.encoding = resp.apparent_encoding or "utf-8"
            parsed = feedparser.parse(resp.content)
            for entry in parsed.entries[:max_items]:
                title = (entry.get("title") or "").strip()
                link = (entry.get("link") or "").strip()
                if not title or not link:
                    continue
                summary_html = entry.get("summary") or entry.get("description") or ""
                summary = self._strip_html(summary_html)
                pub_time = _parse_rfc_time(entry.get("published_parsed") or entry.get("updated_parsed") or entry.get("published") or "")
                result.append(RawNews(
                    url=link,
                    original_title=title,
                    source="",
                    category="",
                    publish_time=pub_time,
                    summary=summary,
                ))
        except Exception as e:
            logger.error(f"RSS 抓取失败 {url}: {e}")
        return result

    def _fetch_html(self, url: str, cfg: Dict[str, Any], max_items: int) -> List[RawNews]:
        result: List[RawNews] = []
        try:
            resp = self.session.get(url, timeout=15)
            resp.encoding = resp.apparent_encoding or "utf-8"
            soup = BeautifulSoup(resp.text, "lxml")

            title_sel = cfg.get("title_selector") or "h1, h2, .title, [class*='title']"
            link_sel = cfg.get("link_selector") or "a[href]"

            candidates = []
            for a in soup.select(link_sel)[:max_items * 3]:
                href = a.get("href", "").strip()
                text = a.get_text(strip=True)
                if not href or not text:
                    continue
                if not href.startswith("http"):
                    base = urlparse(url)
                    href = f"{base.scheme}://{base.netloc}{href}" if href.startswith("/") else f"{url}/{href}"
                candidates.append((text, href))

            seen = set()
            for text, href in candidates:
                if len(result) >= max_items:
                    break
                if href in seen:
                    continue
                seen.add(href)
                result.append(RawNews(
                    url=href,
                    original_title=text,
                    source="",
                    category="",
                    publish_time="",
                    summary="",
                ))
        except Exception as e:
            logger.error(f"HTML 抓取失败 {url}: {e}")
        return result

    def fetch_article_content(self, url: str, max_chars: int = 4000) -> str:
        """抓取文章详情内容（带重试机制）"""
        html = ""
        
        # 重试机制：最多重试2次
        for attempt in range(3):
            try:
                # 使用session而不是直接调用requests.get，复用连接池和headers
                resp = self.session.get(url, timeout=15)
                resp.encoding = resp.apparent_encoding or "utf-8"
                
                if resp.status_code == 200:
                    html = resp.text
                    break
                elif resp.status_code in (403, 429):
                    # 请求被拒绝或限流，等待后重试
                    logger.warning(f"文章抓取被拒绝 {url} (状态码: {resp.status_code})")
                    if attempt < 2:
                        time.sleep(2 ** attempt)
                        continue
                else:
                    logger.warning(f"文章抓取失败 {url} (状态码: {resp.status_code})")
                    break
            except requests.exceptions.Timeout:
                logger.warning(f"文章抓取超时 {url} (第{attempt+1}次)")
                if attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
            except requests.exceptions.ConnectionError:
                logger.warning(f"文章抓取连接失败 {url} (第{attempt+1}次)")
                if attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
            except Exception as e:
                logger.warning(f"文章抓取异常 {url}: {e}")
                break

        if not html:
            return ""

        content = ""
        try:
            soup = BeautifulSoup(html, "lxml")
            for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
                tag.decompose()

            candidates = soup.select("article, .article, .content, [class*='content'], [class*='article'], main")
            if candidates:
                best = max(candidates, key=lambda t: len(t.get_text(" ", strip=True)))
                content = best.get_text("\n", strip=True)
            else:
                paragraphs = soup.find_all("p")
                if paragraphs:
                    content = "\n".join(p.get_text(" ", strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 20)
                else:
                    content = soup.get_text("\n", strip=True)
        except Exception as e:
            logger.warning(f"文章解析失败 {url}: {e}")
            content = ""

        content = re.sub(r"\s+\n", "\n", content)
        content = re.sub(r"\n{3,}", "\n\n", content)
        return content[:max_chars].strip()

    @staticmethod
    def _strip_html(text: str) -> str:
        if not text:
            return ""
        try:
            return BeautifulSoup(text, "lxml").get_text(" ", strip=True)
        except Exception:
            return re.sub(r"<[^>]+>", "", text).strip()
