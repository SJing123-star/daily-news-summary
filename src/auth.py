"""
API认证模块
提供API Key认证和权限控制功能
"""
import os
import time
import logging
from functools import wraps
from collections import defaultdict
from flask import request, jsonify

logger = logging.getLogger(__name__)

# 从环境变量读取API密钥，支持多个密钥用逗号分隔
_API_KEYS = os.environ.get("API_KEYS", "")
_VALID_API_KEYS = set(k.strip() for k in _API_KEYS.split(",") if k.strip())

# 管理员密钥（独立于普通API密钥，用于敏感操作）
_ADMIN_API_KEYS = os.environ.get("ADMIN_API_KEYS", "")
_VALID_ADMIN_KEYS = set(k.strip() for k in _ADMIN_API_KEYS.split(",") if k.strip())

def _get_lock():
    """获取线程锁"""
    try:
        import threading
        return threading.Lock()
    except ImportError:
        return None

# 速率限制存储
_rate_limit_store = defaultdict(list)
_rate_limit_lock = _get_lock()

def _cleanup_rate_limit():
    """清理过期的速率限制记录（需要在锁外调用）"""
    now = time.time()
    for key in list(_rate_limit_store.keys()):
        _rate_limit_store[key] = [t for t in _rate_limit_store[key] if now - t < 60]
        if not _rate_limit_store[key]:
            del _rate_limit_store[key]


def init_api_keys(api_keys: str):
    """初始化API密钥"""
    global _VALID_API_KEYS
    _VALID_API_KEYS = set(k.strip() for k in api_keys.split(",") if k.strip())
    logger.info(f"已加载 {len(_VALID_API_KEYS)} 个API密钥")


def init_admin_keys(admin_keys: str):
    """初始化管理员密钥"""
    global _VALID_ADMIN_KEYS
    _VALID_ADMIN_KEYS = set(k.strip() for k in admin_keys.split(",") if k.strip())
    logger.info(f"已加载 {len(_VALID_ADMIN_KEYS)} 个管理员密钥")


def rate_limited(max_requests: int = 30, window_seconds: int = 60):
    """
    速率限制装饰器
    限制在指定时间窗口内的最大请求数
    
    Args:
        max_requests: 时间窗口内最大请求数，默认30次/分钟
        window_seconds: 时间窗口大小（秒），默认60秒
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # 获取客户端IP
            client_ip = request.remote_addr
            if not client_ip:
                client_ip = request.headers.get("X-Forwarded-For", "unknown").split(",")[0].strip()
            
            now = time.time()
            
            with _rate_limit_lock:
                # 清理过期记录（每100次请求清理一次）
                if len(_rate_limit_store) > 100:
                    # 内联清理逻辑，避免嵌套锁调用导致死锁
                    for key in list(_rate_limit_store.keys()):
                        _rate_limit_store[key] = [t for t in _rate_limit_store[key] if now - t < window_seconds]
                        if not _rate_limit_store[key]:
                            del _rate_limit_store[key]
                
                # 获取该IP的请求时间列表
                timestamps = _rate_limit_store[client_ip]
                
                # 过滤过期请求
                timestamps = [t for t in timestamps if now - t < window_seconds]
                
                if len(timestamps) >= max_requests:
                    # 计算还需等待的时间
                    wait_time = int(window_seconds - (now - timestamps[0]))
                    logger.warning(f"速率限制触发: IP={client_ip}, 请求数={len(timestamps)}")
                    return jsonify({
                        "ok": False,
                        "error": f"请求过于频繁，请 {wait_time} 秒后重试",
                    }), 429
                
                # 添加当前请求时间
                timestamps.append(now)
                _rate_limit_store[client_ip] = timestamps
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def generate_api_key() -> str:
    """生成一个新的随机API密钥"""
    import secrets
    return secrets.token_urlsafe(32)


def _get_api_key_from_request() -> str:
    """从请求中提取API密钥"""
    # 优先从Authorization头获取
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:].strip()
    
    # 其次从X-API-Key头获取
    api_key_header = request.headers.get("X-API-Key", "")
    if api_key_header:
        return api_key_header.strip()
    
    # 最后从查询参数获取
    return request.args.get("api_key", "").strip()


def require_api_key(f):
    """
    API认证装饰器
    需要在请求中提供有效的API密钥
    支持三种方式传递API密钥：
    1. Authorization: Bearer <api_key>
    2. X-API-Key: <api_key>
    3. ?api_key=<api_key>
    
    安全策略：
    - 必须配置API_KEYS环境变量才能使用受保护的API端点
    - 未配置API_KEYS时，受保护端点返回401未授权
    - 开发环境可设置 SKIP_API_AUTH=true 跳过认证（不推荐生产环境使用）
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 开发环境跳过认证（仅用于调试，生产环境必须关闭）
        if os.environ.get("SKIP_API_AUTH", "false").lower() == "true":
            logger.warning("开发模式：跳过API认证（生产环境请禁用）")
            return f(*args, **kwargs)
        
        # 如果没有配置任何API密钥，拒绝所有请求
        if not _VALID_API_KEYS:
            logger.error("API_KEYS环境变量未配置，拒绝访问受保护端点")
            return jsonify({"ok": False, "error": "API_KEYS未配置，请联系管理员"}), 401
        
        api_key = _get_api_key_from_request()
        
        if not api_key:
            logger.warning("请求缺少API密钥")
            return jsonify({"ok": False, "error": "缺少API密钥，请在请求头中提供 X-API-Key 或 Authorization: Bearer <key>"}), 401
        
        if api_key not in _VALID_API_KEYS:
            logger.warning(f"无效的API密钥: {api_key[:8]}...")
            return jsonify({"ok": False, "error": "无效的API密钥"}), 403
        
        logger.debug(f"API认证成功: {api_key[:8]}...")
        return f(*args, **kwargs)
    
    return decorated_function


def require_admin(f):
    """
    管理员权限装饰器
    需要管理员级别的API密钥
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 开发环境跳过认证（仅用于调试，生产环境必须关闭）
        if os.environ.get("SKIP_API_AUTH", "false").lower() == "true":
            logger.warning("开发模式：跳过API认证（生产环境请禁用）")
            return f(*args, **kwargs)
        
        # 如果没有配置任何API密钥，拒绝所有请求
        if not _VALID_API_KEYS:
            logger.error("API_KEYS环境变量未配置，拒绝访问管理员端点")
            return jsonify({"ok": False, "error": "API_KEYS未配置，请联系管理员"}), 401
        
        api_key = _get_api_key_from_request()
        
        if not api_key:
            logger.warning("请求缺少API密钥")
            return jsonify({"ok": False, "error": "缺少API密钥"}), 401
        
        if api_key not in _VALID_API_KEYS:
            logger.warning(f"无效的API密钥: {api_key[:8]}...")
            return jsonify({"ok": False, "error": "无效的API密钥"}), 403
        
        # 管理员权限验证：必须是管理员密钥
        if not _VALID_ADMIN_KEYS:
            logger.warning("ADMIN_API_KEYS环境变量未配置，降级为所有API密钥均有管理员权限")
        elif api_key not in _VALID_ADMIN_KEYS:
            logger.warning(f"API密钥无管理员权限: {api_key[:8]}...")
            return jsonify({"ok": False, "error": "需要管理员权限"}), 403
        
        logger.debug(f"管理员认证成功: {api_key[:8]}...")
        return f(*args, **kwargs)
    
    return decorated_function
