"""Flask Web 应用 — 每日新闻速览的前端界面。

用法:
    python app.py                    # 启动 Web 服务
    浏览器访问 http://127.0.0.1:5000
"""

import logging
import os
import sys
import threading
from datetime import datetime

from flask import Flask, render_template, jsonify, request, redirect, url_for, flash

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config_loader import AppConfig
from src.database import Database
from src.analyzer import NewsAnalyzer
from src.parallel_analyzer import ParallelNewsAnalyzer, PipelineConfig
from src.autostart_manager import AutoStartManager
from src.strategy_manager import StrategyManager
from src.auth import require_api_key, require_admin, rate_limited, init_api_keys, init_admin_keys
from src.utils import is_english

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("app")

app = Flask(__name__)

# 修复硬编码Secret Key问题 - 使用随机生成或环境变量
_app_secret_key = os.environ.get("SECRET_KEY")
if not _app_secret_key:
    import secrets
    _app_secret_key = secrets.token_hex(32)
    logger.warning("SECRET_KEY 未配置，使用随机生成的密钥（重启后会失效）")
app.secret_key = _app_secret_key

app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

_config = None
_analyzer = None
_analyzer_mode = "parallel"  # "parallel" 或 "serial"
_collect_lock = threading.Lock()
_last_collect_result = None

# 初始化API密钥和管理员密钥
init_api_keys(os.environ.get("API_KEYS", ""))
init_admin_keys(os.environ.get("ADMIN_API_KEYS", ""))


def get_config():
    global _config
    if _config is None:
        _config = AppConfig()
    return _config


def get_analyzer():
    global _analyzer
    if _analyzer is None:
        if _analyzer_mode == "parallel":
            pipeline_cfg = PipelineConfig(
                fetch_workers=8,
                content_workers=10,
                summary_workers=3,
                llm_rate_limit=3,
            )
            _analyzer = ParallelNewsAnalyzer(
                config=get_config(), pipeline_config=pipeline_cfg
            )
            logger.info("使用多线程新闻分析器")
        else:
            _analyzer = NewsAnalyzer(config=get_config())
            logger.info("使用单线程新闻分析器")
    return _analyzer


def set_analyzer_mode(mode: str):
    """切换分析器模式：parallel / serial"""
    global _analyzer, _analyzer_mode
    if mode not in ("parallel", "serial"):
        raise ValueError("mode 必须是 'parallel' 或 'serial'")
    _analyzer_mode = mode
    _analyzer = None
    logger.info(f"分析器模式已切换为: {mode}")


def get_db():
    return Database()


@app.route("/")
def index():
    db = get_db()
    category = request.args.get("category", None)
    matched_only = request.args.get("matched", "false").lower() == "true"
    page = int(request.args.get("page", 1))
    page_size = 50

    if category and category.lower() in ("all", ""):
        category = None

    offset = (page - 1) * page_size

    if matched_only:
        news_list = db.get_matched_news(limit=page_size, offset=offset)
        total = db.get_matched_news_count()
        logger.info(f"查询匹配新闻 第 {page} 页，得到 {len(news_list)} 条")
    else:
        news_list = db.get_recent_news(limit=page_size, days=3650, category=category, offset=offset)
        total = db.get_news_count(category=category)
        logger.info(f"查询分类 {category} 第 {page} 页，得到 {len(news_list)} 条新闻")

    total_pages = (total + page_size - 1) // page_size

    stats = db.get_stats()
    category_stats = db.get_category_stats()

    config = get_config()
    sources = [s.get("name") for s in config.news_sources]

    category_list = [cs["category"] for cs in category_stats if cs["category"]]
    if not category_list:
        category_list = ["政治", "经济", "科技", "网络安全"]

    category_counts = {}
    for cs in category_stats:
        category_counts[cs["category"]] = cs["count"]

    return render_template(
            "index.html",
            news_list=news_list,
            stats=stats,
            sources=sources,
            now=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            collect_status=None,
            categories=category_list,
            category_counts=category_counts,
            current_category=category or "all",
            matched_only=matched_only,
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages,
        )


@app.route("/news/<int:news_id>")
def news_detail(news_id):
    db = get_db()
    item = db.get_news_by_id(news_id)
    if not item:
        return "未找到该新闻", 404
    category = item.category or "政治"
    return render_template("detail.html", news=item, category=category)


@app.route("/api/analyze/<int:news_id>", methods=["POST"])
@require_api_key
def api_analyze(news_id):
    analyzer = get_analyzer()
    try:
        brief = analyzer.generate_analysis_for(news_id)
        return jsonify({"ok": True, "brief": brief})
    except Exception as e:
        logger.error(f"分析失败 id={news_id}: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/collect", methods=["POST"])
@require_api_key
@rate_limited(max_requests=5, window_seconds=60)
def api_collect():
    global _last_collect_result, _collect_progress
    if _collect_lock.locked():
        return jsonify({"ok": False, "error": "正在执行中，请稍后再试"}), 429

    def run_collect():
        global _collect_progress
        try:
            analyzer = get_analyzer()
            _collect_progress = {
                "status": "fetching",
                "message": "正在抓取新闻源数据...",
                "progress": 0,
                "stats": {},
            }
            stats = analyzer.run_full_pipeline(progress_callback=update_progress)
            _last_collect_result = {
                "stats": stats,
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            _collect_progress = {
                "status": "completed",
                "message": f"完成！处理源 {stats.get('sources', 0)}，抓取 {stats.get('fetched', 0)} 条，新增 {stats.get('new', 0)} 条，AI 摘要 {stats.get('summarized', 0)} 条",
                "progress": 100,
                "stats": stats,
            }
        except Exception as e:
            logger.error(f"抓取失败: {e}")
            _collect_progress = {
                "status": "error",
                "message": f"错误: {str(e)}",
                "progress": 0,
                "stats": {},
            }

    def update_progress(status, message, progress, stats):
        global _collect_progress
        with _collect_progress_lock:
            _collect_progress = {
                "status": status,
                "message": message,
                "progress": progress,
                "stats": stats,
            }

    threading.Thread(target=run_collect, daemon=True).start()
    return jsonify({"ok": True, "message": "开始抓取..."})


@app.route("/api/retry", methods=["POST"])
@require_api_key
def api_retry():
    try:
        analyzer = get_analyzer()
        count = analyzer.retry_pending_summaries(limit=30)
        return jsonify({"ok": True, "count": count})
    except Exception as e:
        logger.error(f"重试失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/clear", methods=["POST"])
@require_admin
@rate_limited(max_requests=3, window_seconds=60)
def api_clear():
    try:
        confirm = request.json.get("confirm", False) if request.is_json else request.form.get("confirm", False)
        if not confirm:
            return jsonify({"ok": False, "error": "需要确认参数 confirm=true"}), 400
        
        db = get_db()
        with db._get_conn() as conn:
            conn.execute("DELETE FROM news")
            conn.commit()
        logger.info("数据库已清空")
        return jsonify({"ok": True})
    except Exception as e:
        logger.error(f"清空失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/config")
def show_config():
    config = get_config()
    return jsonify({
        "news_sources": config.news_sources,
        "keywords": config.keywords,
        "llm_provider": config.llm_provider,
        "llm_model": config.llm_model,
        "max_items_per_source": config.max_news_per_source,
        "host": config.host,
        "port": config.port,
    })


_collect_progress = {
    "status": "idle",
    "message": "",
    "progress": 0,
    "stats": {},
}
_collect_progress_lock = threading.Lock()


@app.route("/subscriptions")
def subscriptions():
    config = get_config()
    app_config = {
        "fetch_hours": config.fetch_hours,
        "max_news_per_source": config.max_news_per_source,
        "days_to_keep": config.days_to_keep,
        "host": config.host,
        "port": config.port,
        "log_level": config.log_level,
    }
    
    strategies = {}
    for s in config.strategies:
        strategies[s.get("site_type", "")] = s.get("name", "")
    
    sources_with_strategy_name = []
    for src in config.news_sources:
        source_copy = src.copy()
        strategy_type = src.get("strategy", "")
        source_copy["strategy_name"] = strategies.get(strategy_type, strategy_type)
        source_copy["enabled"] = src.get("enabled", True)
        sources_with_strategy_name.append(source_copy)
    
    return render_template(
        "subscriptions.html",
        sources=sources_with_strategy_name,
        app_config=app_config,
    )


@app.route("/strategies")
def strategies():
    return render_template("strategy.html")


@app.route("/llm-management")
def llm_management():
    return render_template("llm_management.html")


@app.route("/api/llm/configs", methods=["GET"])
@require_admin
def api_llm_list():
    try:
        db = get_db()
        configs = db.get_all_llm_configs()
        return jsonify({
            "ok": True,
            "configs": [
                {
                    "id": c.id,
                    "name": c.name,
                    "provider": c.provider,
                    "model": c.model,
                    "base_url": c.base_url,
                    "api_key": "****" if c.api_key else "",
                    "max_tokens": c.max_tokens,
                    "timeout": c.timeout,
                    "temperature": c.temperature,
                    "is_active": c.is_active,
                    "last_test_time": c.last_test_time,
                    "health_status": c.health_status,
                    "avg_response_time": c.avg_response_time,
                }
                for c in configs
            ]
        })
    except Exception as e:
        logger.error(f"获取模型列表失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/llm/configs/<int:config_id>", methods=["GET"])
@require_admin
def api_llm_get(config_id):
    try:
        db = get_db()
        config = db.get_llm_config_by_id(config_id)
        if not config:
            return jsonify({"ok": False, "error": "模型配置不存在"}), 404
        return jsonify({
            "ok": True,
            "config": {
                "id": config.id,
                "name": config.name,
                "provider": config.provider,
                "model": config.model,
                "base_url": config.base_url,
                "api_key": "****" if config.api_key else "",
                "max_tokens": config.max_tokens,
                "timeout": config.timeout,
                "temperature": config.temperature,
                "is_active": config.is_active,
            }
        })
    except Exception as e:
        logger.error(f"获取模型配置失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/llm/configs", methods=["POST"])
@require_admin
def api_llm_create():
    try:
        db = get_db()
        data = request.get_json()
        from src.database import LLMConfig
        
        config = LLMConfig(
            name=data.get("name", ""),
            provider=data.get("provider", "openai"),
            model=data.get("model", ""),
            base_url=data.get("base_url", ""),
            api_key=data.get("api_key", ""),
            max_tokens=int(data.get("max_tokens", 2000)),
            timeout=int(data.get("timeout", 60)),
            temperature=float(data.get("temperature", 0.7)),
            is_active=int(data.get("is_active", 0)),
        )
        
        if not config.name or not config.model:
            return jsonify({"ok": False, "error": "模型名称和模型标识为必填项"}), 400
        
        config_id = db.add_llm_config(config)
        
        if config.is_active:
            db.set_active_llm(config_id)
        
        logger.info(f"已创建模型配置: {config.name}")
        return jsonify({"ok": True, "id": config_id})
    except Exception as e:
        logger.error(f"创建模型配置失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/llm/configs/<int:config_id>", methods=["PUT"])
@require_admin
def api_llm_update(config_id):
    try:
        db = get_db()
        data = request.get_json()
        
        existing = db.get_llm_config_by_id(config_id)
        if not existing:
            return jsonify({"ok": False, "error": "模型配置不存在"}), 404
        
        update_data = {}
        for field in ["name", "provider", "model", "base_url", "api_key", "max_tokens", "timeout", "temperature", "is_active"]:
            if field in data:
                # 安全处理：不更新空的API密钥（避免覆盖已有的密钥）
                if field == "api_key" and not data[field]:
                    continue
                update_data[field] = data[field]
        
        db.update_llm_config(config_id, **update_data)
        
        if data.get("is_active"):
            db.set_active_llm(config_id)
        
        logger.info(f"已更新模型配置: {config_id}")
        return jsonify({"ok": True})
    except Exception as e:
        logger.error(f"更新模型配置失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/llm/configs/<int:config_id>", methods=["DELETE"])
@require_admin
def api_llm_delete(config_id):
    try:
        db = get_db()
        existing = db.get_llm_config_by_id(config_id)
        if not existing:
            return jsonify({"ok": False, "error": "模型配置不存在"}), 404
        
        db.delete_llm_config(config_id)
        logger.info(f"已删除模型配置: {config_id}")
        return jsonify({"ok": True})
    except Exception as e:
        logger.error(f"删除模型配置失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/llm/configs/<int:config_id>/activate", methods=["POST"])
@require_admin
def api_llm_activate(config_id):
    try:
        db = get_db()
        existing = db.get_llm_config_by_id(config_id)
        if not existing:
            return jsonify({"ok": False, "error": "模型配置不存在"}), 404
        
        db.set_active_llm(config_id)
        logger.info(f"已设置当前使用模型: {config_id}")
        return jsonify({"ok": True})
    except Exception as e:
        logger.error(f"设置当前模型失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/llm/test/<int:config_id>", methods=["POST"])
@require_admin
def api_llm_test(config_id):
    import time
    try:
        db = get_db()
        config = db.get_llm_config_by_id(config_id)
        if not config:
            return jsonify({"ok": False, "error": "模型配置不存在"}), 404
        
        if not config.api_key:
            db.update_llm_health(config_id, "error", 0)
            return jsonify({"ok": False, "error": "未配置API密钥", "error_type": "配置错误"}), 400
        
        start_time = time.time()
        error_type = None
        
        try:
            from openai import OpenAI
            client_kwargs = {"api_key": config.api_key, "max_retries": 0}
            if config.base_url:
                client_kwargs["base_url"] = config.base_url
            
            client = OpenAI(**client_kwargs)
            resp = client.chat.completions.create(
                model=config.model,
                messages=[{"role": "user", "content": "Hello, respond with just 'OK'"}],
                max_tokens=10,
                timeout=config.timeout,
            )
            
            response_time_ms = int((time.time() - start_time) * 1000)
            response_time_s = response_time_ms / 1000.0
            
            if resp.choices and len(resp.choices) > 0:
                health_status = "healthy"
                if response_time_ms > 5000:
                    health_status = "warning"
                
                db.update_llm_health(config_id, health_status, response_time_s)
                logger.info(f"模型测试成功: {config.name}, 响应时间: {response_time_ms}ms")
                return jsonify({
                    "ok": True,
                    "response_time": response_time_s,
                    "health_status": health_status,
                })
            else:
                db.update_llm_health(config_id, "error", 0)
                return jsonify({"ok": False, "error": "未收到有效响应", "error_type": "响应异常"}), 400
                
        except Exception as e:
            response_time = int((time.time() - start_time) * 1000)
            error_str = str(e)
            error_type = "未知错误"
            
            if "timeout" in error_str.lower():
                error_type = "请求超时"
            elif "API key" in error_str or "api_key" in error_str or "401" in error_str:
                error_type = "API密钥错误"
            elif "404" in error_str or "model" in error_str.lower():
                error_type = "模型不存在"
            elif "Connection" in error_str or "connect" in error_str.lower():
                error_type = "连接失败"
            elif "rate" in error_str.lower() or "429" in error_str:
                error_type = "速率限制"
            
            db.update_llm_health(config_id, "error", 0)
            logger.error(f"模型测试失败: {config.name}, {error_type}: {error_str}")
            return jsonify({
                "ok": False,
                "error": error_str[:200],
                "error_type": error_type,
                "response_time": response_time,
            }), 400
    
    except Exception as e:
        logger.error(f"测试接口异常: {e}")
        return jsonify({"ok": False, "error": str(e), "error_type": "系统错误"}), 500


@app.route("/api/subscriptions", methods=["POST"])
@require_admin
def api_subscriptions():
    global _config, _analyzer
    try:
        data = request.get_json()
        sources = data.get("sources", [])
        config = get_config()
        config.save_sources(sources)
        _config = None
        _analyzer = None
        logger.info(f"已保存 {len(sources)} 个新闻源")
        return jsonify({"ok": True})
    except Exception as e:
        logger.error(f"保存订阅失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/test-source", methods=["POST"])
@require_admin
def api_test_source():
    try:
        import time
        import requests
        from src.scraper import Scraper, _safe_headers
        
        data = request.get_json()
        source = data.get("source", {})
        
        if not source or not source.get("url") or not source.get("type"):
            return jsonify({"ok": False, "error": "缺少必要的新闻源参数"}), 400
        
        url = source.get("url")
        start_time = time.time()
        
        try:
            session = requests.Session()
            session.headers.update(_safe_headers())
            
            resp = session.get(url, timeout=10)
            resp.raise_for_status()
            
            if resp.status_code == 200:
                scraper = Scraper(min_title_length=8)
                items = scraper.fetch_source(source, max_items=3)
                response_time = int((time.time() - start_time) * 1000)
                
                if len(items) == 0:
                    logger.warning(f"新闻源检测返回0条: {source.get('name')}, 可能是内容解析失败")
                    return jsonify({
                        "ok": False,
                        "error": "网络请求成功但未解析到新闻内容",
                        "error_type": "内容解析失败",
                        "response_time": response_time,
                    })
                
                logger.info(f"新闻源检测成功: {source.get('name')}, 获取 {len(items)} 条新闻")
                return jsonify({
                    "ok": True,
                    "count": len(items),
                    "response_time": response_time,
                })
        
        except requests.exceptions.RequestException as e:
            response_time = int((time.time() - start_time) * 1000)
            error_str = str(e)
            error_type = "抓取失败"
            
            if "NameResolutionError" in error_str or "getaddrinfo" in error_str:
                error_type = "DNS解析失败"
            elif "Connection refused" in error_str or "Connection reset" in error_str:
                error_type = "连接被拒绝"
            elif "timeout" in error_str.lower():
                error_type = "请求超时"
            elif "403" in error_str:
                error_type = "访问被拒绝(403)"
            elif "404" in error_str:
                error_type = "页面不存在(404)"
            elif "SSL" in error_str or "certificate" in error_str.lower():
                error_type = "SSL证书错误"
            elif "401" in error_str:
                error_type = "未授权访问(401)"
            elif "500" in error_str:
                error_type = "服务器错误(500)"
            elif "502" in error_str or "503" in error_str or "504" in error_str:
                error_type = "服务不可用"
            
            logger.error(f"新闻源检测失败: {source.get('name')}, {error_type}: {error_str}")
            return jsonify({
                "ok": False,
                "error": error_str[:200],
                "error_type": error_type,
                "response_time": response_time,
            })
    
    except Exception as e:
        logger.error(f"测试新闻源接口异常: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/config", methods=["POST"])
@require_admin
def api_config():
    global _config, _analyzer
    try:
        data = request.get_json()
        app_config = data.get("app", {})
        config = get_config()
        config.save_app_config(app_config)
        _config = None
        _analyzer = None
        logger.info(f"已保存应用配置: {app_config}")
        return jsonify({"ok": True})
    except Exception as e:
        logger.error(f"保存配置失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/collect/progress")
def api_collect_progress():
    with _collect_progress_lock:
        return jsonify(_collect_progress)


@app.route("/api/news/filter", methods=["GET"])
@require_api_key
def api_news_filter():
    try:
        db = get_db()
        start_date = request.args.get("start_date", "")
        end_date = request.args.get("end_date", "")
        category = request.args.get("category", "")
        
        if not start_date or not end_date:
            return jsonify({"ok": False, "error": "请提供开始日期和结束日期"}), 400
        
        try:
            datetime.strptime(start_date, "%Y-%m-%d")
            datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            return jsonify({"ok": False, "error": "日期格式不正确，请使用 YYYY-MM-DD 格式"}), 400
        
        news_list = db.get_news_by_date_range(start_date, end_date, category, limit=200)
        
        return jsonify({
            "ok": True,
            "count": len(news_list),
            "news": [
                {
                    "id": n.id,
                    "title": n.title,
                    "original_title": n.original_title,
                    "source": n.source,
                    "category": n.category,
                    "publish_time": n.publish_time,
                    "one_line_summary": n.one_line_summary,
                    "is_highlighted": n.is_highlighted,
                    "is_strategy_matched": n.is_strategy_matched,
                    "is_analysis_done": n.is_analysis_done,
                }
                for n in news_list
            ]
        })
    except Exception as e:
        logger.error(f"日期筛选失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/strategies", methods=["GET"])
@require_admin
def api_strategies_get():
    global _analyzer
    try:
        analyzer = get_analyzer()
        strategies = analyzer.strategy_manager.get_all_strategies()
        return jsonify({"ok": True, "strategies": strategies})
    except Exception as e:
        logger.error(f"获取策略失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/strategies", methods=["POST"])
@require_admin
def api_strategies_save():
    global _config, _analyzer
    try:
        data = request.get_json()
        strategies = data.get("strategies", [])
        config = get_config()
        config.save_strategies(strategies)
        _config = None
        _analyzer = None
        logger.info(f"已保存策略配置: {len(strategies)} 个策略")
        return jsonify({"ok": True})
    except Exception as e:
        logger.error(f"保存策略失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/strategies/test", methods=["POST"])
@require_admin
def api_strategies_test():
    global _analyzer
    try:
        data = request.get_json()
        site_type = data.get("site_type")
        test_data = data.get("test_data", [])
        analyzer = get_analyzer()
        results = analyzer.strategy_manager.test_strategy(site_type, test_data)
        return jsonify({"ok": True, "results": results})
    except Exception as e:
        logger.error(f"测试策略失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/strategies/<site_type>", methods=["GET"])
def api_strategy_get(site_type):
    global _analyzer
    try:
        analyzer = get_analyzer()
        strategy = analyzer.strategy_manager.get_strategy(site_type)
        if strategy:
            strategies = analyzer.strategy_manager.get_all_strategies()
            found = next((s for s in strategies if s["site_type"] == site_type), None)
            return jsonify({"ok": True, "strategy": found})
        return jsonify({"ok": False, "error": "策略不存在"}), 404
    except Exception as e:
        logger.error(f"获取策略失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/strategies/<site_type>", methods=["PUT"])
@require_admin
def api_strategy_update(site_type):
    global _config, _analyzer
    try:
        data = request.get_json()
        config = data.get("strategy", {})
        analyzer = get_analyzer()
        success = analyzer.strategy_manager.update_strategy(site_type, config)
        if success:
            config_obj = get_config()
            strategies = analyzer.strategy_manager.get_all_strategies()
            config_obj.save_strategies(strategies)
            _config = None
            _analyzer = None
            logger.info(f"已更新策略: {site_type}")
            return jsonify({"ok": True})
        return jsonify({"ok": False, "error": "策略更新失败"}), 500
    except Exception as e:
        logger.error(f"更新策略失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/strategies/<site_type>", methods=["DELETE"])
@require_admin
def api_strategy_delete(site_type):
    global _config, _analyzer
    try:
        analyzer = get_analyzer()
        success = analyzer.strategy_manager.delete_strategy(site_type)
        if success:
            config_obj = get_config()
            strategies = analyzer.strategy_manager.get_all_strategies()
            config_obj.save_strategies(strategies)
            _config = None
            _analyzer = None
            logger.info(f"已删除策略: {site_type}")
            return jsonify({"ok": True})
        return jsonify({"ok": False, "error": "策略删除失败"}), 500
    except Exception as e:
        logger.error(f"删除策略失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/autostart/status", methods=["GET"])
def api_autostart_status():
    try:
        manager = AutoStartManager()
        status = manager.get_status()
        return jsonify({"ok": True, **status})
    except Exception as e:
        logger.error(f"获取自启动状态失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/autostart/enable", methods=["POST"])
@require_admin
def api_autostart_enable():
    try:
        manager = AutoStartManager()
        result = manager.enable()
        if result.get("ok"):
            logger.info("自启动已启用")
        return jsonify(result)
    except Exception as e:
        logger.error(f"启用自启动失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/autostart/disable", methods=["POST"])
@require_admin
def api_autostart_disable():
    try:
        manager = AutoStartManager()
        result = manager.disable()
        if result.get("ok"):
            logger.info("自启动已禁用")
        return jsonify(result)
    except Exception as e:
        logger.error(f"禁用自启动失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


_rematch_progress = {
    "status": "idle",
    "message": "",
    "progress": 0,
    "stats": {},
}
_rematch_cancel_flag = False
_rematch_lock = threading.Lock()
_rematch_progress_lock = threading.Lock()


# is_english 函数已移至 src/utils.py，统一使用工具模块


def get_strategy_for_source(strategy_manager, source_name, category):
    source_name_lower = source_name.lower()
    category_strategy_map = {
        "网络安全": "cybersecurity",
        "科技": "technology",
        "政治": "chinese",
        "经济": "chinese",
    }
    if category in category_strategy_map:
        strategy = strategy_manager.get_strategy(category_strategy_map[category])
        if strategy:
            return strategy
    if "darkreading" in source_name_lower or "securityweek" in source_name_lower or "hacker" in source_name_lower:
        strategy = strategy_manager.get_strategy("cybersecurity")
        if strategy:
            return strategy
    if "36kr" in source_name_lower or "tech" in source_name_lower:
        strategy = strategy_manager.get_strategy("technology")
        if strategy:
            return strategy
    return strategy_manager.get_strategy("chinese") or strategy_manager.get_default_strategy()


@app.route("/api/rematch", methods=["POST"])
@require_admin
@rate_limited(max_requests=3, window_seconds=300)
def api_rematch():
    global _rematch_cancel_flag, _rematch_progress
    if _rematch_lock.locked():
        return jsonify({"ok": False, "error": "正在执行中，请稍后再试"}), 429

    _rematch_cancel_flag = False
    with _rematch_progress_lock:
        _rematch_progress = {
            "status": "running",
            "message": "开始重新匹配关键词...",
            "progress": 0,
            "stats": {},
        }

    def run_rematch():
        global _rematch_cancel_flag, _rematch_progress
        try:
            config = get_config()
            strategies_config = config.strategies
            strategy_manager = StrategyManager(strategies_config)

            db = Database()
            news_list = db.get_recent_news(limit=10000, days=3650)

            if not news_list:
                with _rematch_progress_lock:
                    _rematch_progress = {
                        "status": "completed",
                        "message": "没有新闻数据需要匹配",
                        "progress": 100,
                        "stats": {"total": 0, "matched": 0, "not_matched": 0, "updated": 0, "translated": 0},
                    }
                return

            total = len(news_list)
            stats = {
                "total": total,
                "matched": 0,
                "not_matched": 0,
                "updated": 0,
                "translated": 0,
                "strategies_used": {},
                "categories_updated": {},
                "keyword_distribution": {},
                "category_matches": {},
            }

            with _rematch_progress_lock:
                _rematch_progress = {
                    "status": "running",
                    "message": f"开始处理 {total} 条新闻...",
                    "progress": 0,
                    "stats": stats,
                }

            strategy_cache = {}
            def get_cached_strategy(source_name, category):
                key = f"{source_name}_{category}"
                if key not in strategy_cache:
                    strategy_cache[key] = get_strategy_for_source(strategy_manager, source_name, category)
                return strategy_cache[key]

            batch_updates = []

            for i, news in enumerate(news_list):
                if _rematch_cancel_flag:
                    with _rematch_progress_lock:
                        _rematch_progress = {
                            "status": "cancelled",
                            "message": "用户已中断匹配操作",
                            "progress": int(i / total * 100),
                            "stats": stats,
                        }
                    return

                match_title = news.title or news.original_title

                strategy = get_cached_strategy(news.source, news.category)

                is_match, weight, matched_kws = strategy.match(match_title, "")

                stats["strategies_used"][strategy.site_type] = stats["strategies_used"].get(strategy.site_type, 0) + 1

                old_strategy_matched = news.is_strategy_matched
                new_strategy_matched = 1 if is_match else 0

                if old_strategy_matched != new_strategy_matched:
                    batch_updates.append((new_strategy_matched, news.id))
                    stats["updated"] += 1
                    stats["categories_updated"][news.category] = stats["categories_updated"].get(news.category, 0) + 1

                if is_match:
                    stats["matched"] += 1
                    stats["category_matches"][news.category] = stats["category_matches"].get(news.category, 0) + 1
                    for kw in matched_kws:
                        stats["keyword_distribution"][kw] = stats["keyword_distribution"].get(kw, 0) + 1
                else:
                    stats["not_matched"] += 1

                if (i + 1) % 50 == 0 or i + 1 == total:
                    if batch_updates:
                        db.update_news_strategy_matched_batch(batch_updates)
                        batch_updates = []

                    progress = int((i + 1) / total * 100)
                    with _rematch_progress_lock:
                        _rematch_progress = {
                            "status": "running",
                            "message": f"处理进度: {i + 1}/{total} (已匹配: {stats['matched']}, 已翻译: {stats['translated']})",
                            "progress": progress,
                            "stats": stats,
                        }

            if batch_updates:
                db.update_news_strategy_matched_batch(batch_updates)

            with _rematch_progress_lock:
                _rematch_progress = {
                    "status": "completed",
                    "message": f"匹配完成！共处理 {total} 条新闻，匹配成功 {stats['matched']} 条，状态变更 {stats['updated']} 条",
                    "progress": 100,
                    "stats": stats,
                }

        except Exception as e:
            logger.error(f"重新匹配失败: {e}")
            with _rematch_progress_lock:
                _rematch_progress = {
                    "status": "error",
                    "message": f"错误: {str(e)}",
                    "progress": 0,
                    "stats": {},
                }

    threading.Thread(target=run_rematch, daemon=True).start()
    return jsonify({"ok": True, "message": "开始重新匹配关键词..."})


@app.route("/api/rematch/progress")
def api_rematch_progress():
    with _rematch_progress_lock:
        return jsonify(_rematch_progress)


@app.route("/api/rematch/cancel", methods=["POST"])
def api_rematch_cancel():
    global _rematch_cancel_flag
    _rematch_cancel_flag = True
    return jsonify({"ok": True, "message": "已发送中断信号"})


@app.route("/api/rematch/results")
def api_rematch_results():
    db = Database()
    news_list = db.get_recent_news(limit=10000, days=3650)
    
    results = []
    for news in news_list:
        results.append({
            "id": news.id,
            "title": news.title,
            "original_title": news.original_title,
            "source": news.source,
            "category": news.category,
            "publish_time": news.publish_time,
            "is_highlighted": news.is_highlighted,
            "is_strategy_matched": news.is_strategy_matched,
        })
    
    stats = db.get_stats()
    category_stats = db.get_category_stats()
    
    return jsonify({
        "ok": True,
        "results": results,
        "stats": stats,
        "category_stats": category_stats,
    })


@app.route("/api/rematch/export", methods=["GET"])
def api_rematch_export():
    import csv
    from io import StringIO
    
    db = Database()
    news_list = db.get_recent_news(limit=10000, days=3650)
    
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "标题", "原文标题", "来源", "分类", "发布时间", "关键词命中"])
    
    for news in news_list:
        writer.writerow([
            news.id,
            news.title,
            news.original_title,
            news.source,
            news.category,
            news.publish_time,
            "是" if news.is_highlighted else "否",
        ])
    
    output.seek(0)
    from flask import Response
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=news_keyword_match_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        },
    )


if __name__ == "__main__":
    cfg = get_config()
    logger.info(f"启动 Flask 服务: http://%s:%d", cfg.host, cfg.port)
    app.run(host=cfg.host, port=cfg.port, debug=False)
