"""
工具函数模块
"""

import hashlib
import logging
import re
import time
from datetime import datetime, date
from typing import Optional

logger = logging.getLogger(__name__)


def setup_logging(level: int = logging.INFO) -> None:
    """配置日志"""
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def get_today_str() -> str:
    """获取今日日期字符串"""
    return date.today().strftime("%Y-%m-%d")


def clean_text(text: str) -> str:
    """
    清理文本：去除多余空白、特殊字符等

    Args:
        text: 原始文本

    Returns:
        清理后的文本
    """
    if not text:
        return ""
    # 替换连续空白为单个空格
    text = re.sub(r'\s+', ' ', text)
    # 去除首尾空白
    text = text.strip()
    # 去除零宽字符
    text = re.sub(r'[\u200b\u200c\u200d\ufeff]', '', text)
    return text


def truncate_text(text: str, max_length: int = 3000, suffix: str = "...") -> str:
    """
    截断文本到指定长度

    Args:
        text: 原始文本
        max_length: 最大长度
        suffix: 截断后缀

    Returns:
        截断后的文本
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def generate_hash(text: str) -> str:
    """生成文本的 MD5 哈希值，用于去重"""
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def format_duration(seconds: float) -> str:
    """格式化时长"""
    if seconds < 60:
        return f"{seconds:.1f}秒"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes}分{secs}秒"
