"""
工具函数模块
"""
import re
import uuid
import json
from pathlib import Path
from urllib.parse import urlparse
from typing import Optional, Any, Dict, List


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


def get_android_device_properties(device_id: Optional[str] = None) -> str:
    """生成Android设备属性JSON字符串"""
    if not device_id:
        device_id = generate_device_id()
    
    # 生成一个随机的android_id (16位hex)
    android_id = uuid.uuid4().hex[:16]
    
    props = {
        "uuid": device_id,
        "android_id": android_id,
        "oaid": "",
        "vaid": "",
        "aaid": ""
    }
    
    import json
    return json.dumps(props, separators=(',', ':'))



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


def get_display_width(s: str) -> int:
    """计算字符串在终端中的显示宽度，考虑中文字符"""
    width = 0
    for char in str(s):
        # 基本判断：中文字符通常占用两个单元格
        if ord(char) > 0x4e00 and ord(char) < 0x9fa5:
            width += 2
        else:
            width += 1
    return width


def print_table(headers: list[str], rows: list[list[Any]]) -> None:
    """在终端打印格式化的表格"""
    if not rows:
        # 如果没有数据，只打印表头
        widths = [get_display_width(h) for h in headers]
        header_line = " | ".join(f"{h}" + " " * (widths[i] - get_display_width(h)) for i, h in enumerate(headers))
        print(header_line)
        print("-" * (sum(widths) + 3 * (len(headers) - 1)))
        return

    # 计算每列的最大宽度
    widths = [get_display_width(h) for h in headers]
    for row in rows:
        for i, val in enumerate(row):
            widths[i] = max(widths[i], get_display_width(val))

    # 打印表头
    header_parts = []
    for i, h in enumerate(headers):
        padding = " " * (widths[i] - get_display_width(h))
        header_parts.append(f"{h}{padding}")
    print(" | ".join(header_parts))

    # 打印分隔线
    print("-" * (sum(widths) + 3 * (len(headers) - 1)))

    # 打印行
    for row in rows:
        row_parts = []
        for i, val in enumerate(row):
            padding = " " * (widths[i] - get_display_width(val))
            row_parts.append(f"{val}{padding}")
        print(" | ".join(row_parts))


def save_metadata_files(metadata: Dict[str, Any], output_dir: Path, filename_base: str) -> None:
    """将元数据保存为JSON和Markdown格式"""
    # 确保输出目录存在
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 保存为 JSON
    json_path = output_dir / f"{filename_base}.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    
    # 保存为 Markdown
    md_path = output_dir / f"{filename_base}.md"
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(f"# {metadata.get('title', filename_base)}\n\n")
        
        # 基本信息表格
        f.write("## 基本信息\n\n")
        f.write("| 属性 | 内容 |\n")
        f.write("| --- | --- |\n")
        
        # 提取关键字段
        fields = {
            "作者/播客": metadata.get("author") or metadata.get("podcast", {}).get("title"),
            "发布日期": metadata.get("pubDate"),
            "时长": f"{metadata.get('duration', 0) // 60} 分钟" if metadata.get('duration') else None,
            "播放量": metadata.get("playCount"),
            "ID": metadata.get("eid") or metadata.get("pid")
        }
        
        for key, value in fields.items():
            if value is not None:
                f.write(f"| {key} | {value} |\n")
        
        # 简介/描述
        description = metadata.get("description") or metadata.get("brief")
        if description:
            f.write("\n## 简介\n\n")
            f.write(description)
            f.write("\n")
