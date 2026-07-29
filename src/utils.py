"""
工具函数模块
提供项目中多个模块共享的通用工具函数
"""
import re


def is_english(text: str) -> bool:
    """
    判断文本是否为英文
    
    判断依据：ASCII字符占比超过80%视为英文
    
    Args:
        text: 待检测的文本
        
    Returns:
        bool: 如果是英文返回True，否则返回False
    """
    if not text:
        return False
    ascii_chars = sum(1 for c in text if ord(c) < 128)
    return ascii_chars > len(text) * 0.8


def clean_text(text: str) -> str:
    """
    清理文本：移除特殊字符，统一空格
    
    Args:
        text: 待清理的文本
        
    Returns:
        str: 清理后的文本
    """
    if not text:
        return ""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s\u4e00-\u9fff]', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text


def escape_html(text: str) -> str:
    """
    HTML转义，防止XSS攻击
    
    Args:
        text: 待转义的文本
        
    Returns:
        str: 转义后的文本
    """
    if not text:
        return ""
    escape_map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;',
    }
    return ''.join(escape_map.get(c, c) for c in text)


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    截断文本到指定长度
    
    Args:
        text: 待截断的文本
        max_length: 最大长度
        suffix: 截断后的后缀
        
    Returns:
        str: 截断后的文本
    """
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[:max_length].rstrip() + suffix
