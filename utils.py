"""
工具函数模块
"""
import re
import uuid
from pathlib import Path
from urllib.parse import urlparse
from typing import Optional


def sanitize_filename(filename: str, max_length: int = 200) -> str:
    """清理文件名，移除非法字符"""
    # 移除或替换Windows/Linux不允许的字符
    illegal_chars = r'[<>:"/\\|?*]'
    filename = re.sub(illegal_chars, '_', filename)
    # 移除前后空格
    filename = filename.strip()
    # 限制长度
    if len(filename) > max_length:
        filename = filename[:max_length]
    return filename


def format_size(size_bytes: int) -> str:
    """将字节转换为MB格式"""
    if size_bytes == 0:
        return "0 MB"
    size_mb = size_bytes / (1024 * 1024)
    return f"{size_mb:.2f} MB"


def get_file_extension(url: str) -> str:
    """从URL获取文件扩展名"""
    parsed_url = urlparse(url)
    path = parsed_url.path
    if path.endswith('.m4a'):
        return '.m4a'
    elif path.endswith('.mp3'):
        return '.mp3'
    elif path.endswith('.wav'):
        return '.wav'
    else:
        return '.m4a'  # 默认扩展名


def generate_device_id() -> str:
    """生成设备ID"""
    return str(uuid.uuid4())


def create_directory(path: Path) -> Path:
    """创建目录"""
    path.mkdir(parents=True, exist_ok=True)
    return path


def validate_phone_number(phone: str) -> bool:
    """验证手机号格式"""
    # 简单的手机号验证
    pattern = r'^1[3-9]\d{9}$'
    return bool(re.match(pattern, phone))


def validate_area_code(area_code: str) -> bool:
    """验证区号格式"""
    # 简单的区号验证
    pattern = r'^\+\d{1,4}$'
    return bool(re.match(pattern, area_code))


def extract_podcast_id_from_url(url_or_id: str) -> Optional[str]:
    """从URL或直接输入中提取播客ID"""
    # 如果已经是ID格式，直接返回
    if re.match(r'^[0-9a-f]{24}$', url_or_id):
        return url_or_id

    # 尝试从URL中提取ID
    url_patterns = [
        r'https?://(?:www\.)?xiaoyuzhoufm\.com/podcast/([0-9a-f]{24})',
        r'xiaoyuzhoufm\.com/podcast/([0-9a-f]{24})',
        r'/podcast/([0-9a-f]{24})',
        r'([0-9a-f]{24})'
    ]

    for pattern in url_patterns:
        match = re.search(pattern, url_or_id)
        if match:
            return match.group(1)

    return None


def extract_episode_id_from_url(url_or_id: str) -> Optional[str]:
    """从单集URL中提取单集ID"""
    # 如果已经是ID格式，直接返回
    if re.match(r'^[0-9a-f]{24}$', url_or_id):
        return url_or_id

    # 尝试从URL中提取单集ID
    # 支持的URL格式：
    url_patterns = [
        r'https?://(?:www\.)?xiaoyuzhoufm\.com/episode/([0-9a-f]{24})',
        r'xiaoyuzhoufm\.com/episode/([0-9a-f]{24})',
        r'/episode/([0-9a-f]{24})',
    ]

    for pattern in url_patterns:
        match = re.search(pattern, url_or_id)
        if match:
            return match.group(1)

    return None


def detect_input_type(user_input: str) -> tuple[str, Optional[str]]:
    """检测用户输入类型并提取ID"""
    # 首先尝试单集URL
    episode_id = extract_episode_id_from_url(user_input)
    if episode_id:
        return "episode", episode_id

    # 然后尝试播客URL或ID
    podcast_id = extract_podcast_id_from_url(user_input)
    if podcast_id:
        return "podcast", podcast_id

    return "unknown", None


def is_valid_podcast_id(podcast_id: str) -> bool:
    """验证播客ID格式"""
    if not podcast_id:
        return False
    # 播客ID通常是24位的十六进制字符串
    return bool(re.match(r'^[0-9a-f]{24}$', podcast_id))
