"""
下载器模块
"""
import sys
import time
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Any
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from tqdm import tqdm

try:
    from .auth import XiaoyuzhouAuth
    from .config import config
    from .utils import sanitize_filename, format_size, get_file_extension, create_directory
except ImportError:
    # 如果作为独立模块运行
    from auth import XiaoyuzhouAuth
    from config import config
    from utils import sanitize_filename, format_size, get_file_extension, create_directory


class XiaoyuzhouDownloader:
    """小宇宙播客下载器"""

    def __init__(self, auth: Optional[XiaoyuzhouAuth] = None):
        self.auth = auth or XiaoyuzhouAuth()

        # 确保认证
        if not self.auth.ensure_authenticated():
            print("认证失败，无法创建下载器")
            return None

        self.api = self.auth.get_api()
        if not self.api:
            print("获取API实例失败")
            return None

        # 创建带重试机制的session
        self.download_session = self.create_robust_session()

    def create_robust_session(self):
        """创建具有重试机制的下载会话"""
        session = requests.Session()

        # 配置重试策略
        retry_strategy = Retry(
            total=config.get('download.max_retries', 3),
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        # 设置超时
        session.timeout = config.get('download.timeout', 60)

        return session

    def create_download_directory(self, podcast_title: str) -> Path:
        """创建下载目录"""
        safe_title = sanitize_filename(podcast_title)
        download_dir = config.download_dir / safe_title
        return create_directory(download_dir)

    def download_file(self, url: str, filepath: Path, episode_title: str, episode_index: int) -> bool:
        """下载单个文件，支持断点续传和重试机制，简化输出"""
        if not url:
            return False

        # 检查文件是否已存在
        if filepath.exists():
            file_size = filepath.stat().st_size
            print(f"\r✅ [{episode_index:03d}] {episode_title[:50]} ({format_size(file_size)}) [已存在]",
                  file=sys.stderr, flush=True)
            return True

        max_retries = config.get('download.max_retries', 3)
        retry_delay = config.get('download.retry_delay', 2)

        for attempt in range(max_retries + 1):
            try:
                return self._download_file_attempt(url, filepath, episode_title, episode_index, attempt)
            except Exception as e:
                # 如果是最后一次尝试，记录失败
                if attempt == max_retries:
                    print(f"\r❌ [{episode_index:03d}] {episode_title[:50]} - 下载失败: {e}",
                          file=sys.stderr, flush=True)
                    return False

                # 等待后重试
                time.sleep(retry_delay)

        return False

    def _download_file_attempt(self, url: str, filepath: Path, episode_title: str, episode_index: int, attempt: int) -> bool:
        """单次下载尝试，带进度条显示"""
        # 获取已下载的文件大小（用于断点续传）
        temp_filepath = filepath.with_suffix(filepath.suffix + '.tmp')
        resume_header = {}
        resume_pos = 0

        if temp_filepath.exists():
            resume_pos = temp_filepath.stat().st_size
            resume_header['Range'] = f'bytes={resume_pos}-'

        # 发起下载请求，使用带重试机制的session
        response = self.download_session.get(
            url,
            headers=resume_header,
            stream=True,
            timeout=config.get('download.timeout', 60)
        )
        response.raise_for_status()

        # 获取文件总大小
        content_length = response.headers.get('content-length')
        if content_length:
            total_size = int(content_length) + resume_pos
        else:
            total_size = None

        # 创建进度条
        progress_desc = f"[{episode_index:03d}] {episode_title[:40]}"
        progress_bar = tqdm(
            total=total_size,
            initial=resume_pos,
            unit='B',
            unit_scale=True,
            unit_divisor=1024,
            desc=progress_desc,
            leave=False,  # 下载完成后清除进度条
            ncols=100,    # 进度条宽度
            file=sys.stderr  # 输出到stderr避免干扰正常输出
        )

        try:
            # 写入文件
            mode = 'ab' if resume_header and temp_filepath.exists() else 'wb'
            chunk_size = config.get('download.chunk_size', 8192)

            with open(temp_filepath, mode) as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        progress_bar.update(len(chunk))

            # 下载完成后重命名文件
            temp_filepath.rename(filepath)
            progress_bar.close()

            # 显示完成信息
            file_size = filepath.stat().st_size if filepath.exists() else 0
            print(f"\r✅ [{episode_index:03d}] {episode_title[:50]} ({format_size(file_size)})",
                  file=sys.stderr, flush=True)

            return True

        except Exception as e:
            progress_bar.close()
            raise e

    def save_data_json(self, pid: str, episodes_data: Dict[str, Any]) -> Path:
        """保存JSON数据到data目录，以ID命名"""
        data_dir = create_directory(config.data_dir)
        data_file = data_dir / f"{pid}.json"

        with open(data_file, 'w', encoding='utf-8') as f:
            json.dump(episodes_data, f, ensure_ascii=False, indent=2)

        print(f"💾 JSON数据已保存: {data_file}", file=sys.stderr)
        return data_file

    def load_from_json(self, json_file: str) -> Dict[str, Any]:
        """从JSON文件加载数据"""
        json_path = Path(json_file)
        if not json_path.exists():
            raise FileNotFoundError(f"JSON文件不存在: {json_file}")

        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        print(f"📂 从JSON文件加载数据: {json_file}", file=sys.stderr)
        return data

    def save_metadata(self, podcast_data: Dict, episodes: List[Dict], download_dir: Path):
        """保存播客元数据到下载目录"""
        metadata = {
            "podcast": podcast_data,
            "episodes": episodes,
            "total_episodes": len(episodes),
            "download_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        metadata_file = download_dir / "metadata.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        print(f"💾 元数据已保存: {metadata_file}", file=sys.stderr)
        return metadata_file

    def get_all_episodes(self, pid: str, max_episodes: Optional[int] = None) -> List[Dict]:
        """获取所有单集数据（支持分页）"""
        all_episodes = []
        load_more_key = None
        page_count = 0

        print(f"📋 获取播客单集列表...", file=sys.stderr, end='', flush=True)

        while True:
            page_count += 1

            try:
                result = self.api.get_episodes_page(pid, load_more_key)

                if not result["success"]:
                    print(f"\n❌ 第 {page_count} 页获取失败: {result['error']}", file=sys.stderr)
                    break

                data = result["data"]
                episodes = data.get('data', [])

                if not episodes:
                    break

                all_episodes.extend(episodes)

                # 使用简洁的进度指示器
                print('.', end='', file=sys.stderr, flush=True)

                # 检查是否达到最大数量限制
                if max_episodes and len(all_episodes) >= max_episodes:
                    all_episodes = all_episodes[:max_episodes]
                    break

                # 检查是否还有更多数据
                if len(episodes) < 15:  # 如果返回的数据少于请求的limit，说明没有更多数据
                    break

                # 生成下一页的loadMoreKey
                last_episode = episodes[-1]
                load_more_key = {
                    "direction": "NEXT",
                    "pubDate": last_episode.get("pubDate"),
                    "id": last_episode.get("eid")
                }

                # 添加延时避免请求过快
                time.sleep(0.5)

            except Exception as e:
                print(f"\n❌ 第 {page_count} 页获取失败: {e}", file=sys.stderr)
                break

        # 完成后显示总结
        limit_info = f" (限制 {max_episodes} 个)" if max_episodes else ""
        print(f" 完成！共获取 {len(all_episodes)} 个单集{limit_info}", file=sys.stderr)

        return all_episodes

    def download_episodes_sequential(self, episodes: List[Dict], download_dir: Path) -> tuple:
        """单线程顺序下载单集"""
        success_count = 0
        episode_metadata = []
        download_tasks = []

        # 准备下载任务
        for i, episode in enumerate(episodes, 1):
            episode_title = episode.get('title', f'Episode_{i}')
            enclosure_url = episode.get('enclosure', {}).get('url', '')
            is_private_media = episode.get('isPrivateMedia', False)
            eid = episode.get('eid', '')

            # 处理付费音频
            if is_private_media:
                print(f"💰 [{i:03d}] 检测到付费内容: {episode_title}")

                # 检查URL是否已经包含private-media域名，如果是则说明已经有权限
                if enclosure_url and "private-media.xyzcdn.net" in enclosure_url:
                    print(f"✅ [{i:03d}] 已有权限，正在下载付费内容")
                else:
                    # 尝试获取私有媒体URL
                    private_result = self.api.get_private_media_url(eid)

                    if private_result["success"]:
                        private_data = private_result["data"]
                        if "data" in private_data and "url" in private_data["data"]:
                            enclosure_url = private_data["data"]["url"]
                            print(f"✅ [{i:03d}] 获取到付费音频链接，可下载付费内容")
                        else:
                            print(f"❌ [{i:03d}] 无访问权限，跳过: {episode_title}")
                            continue
                    else:
                        print(f"❌ [{i:03d}] 无访问权限，跳过: {episode_title}")
                        continue

            if not enclosure_url:
                print(f"  ⚠️  [{i:03d}] 跳过: 无音频链接 - {episode_title}")
                continue

            # 生成安全的文件名
            safe_title = sanitize_filename(episode_title)
            file_extension = get_file_extension(enclosure_url)
            filename = f"{i:03d}. {safe_title}{file_extension}"
            filepath = download_dir / filename

            download_tasks.append({
                'episode': episode,
                'episode_title': episode_title,
                'enclosure_url': enclosure_url,
                'filepath': filepath,
                'filename': filename,
                'episode_index': i,
                'is_private_media': is_private_media
            })

        print(f"🚀 开始顺序下载 {len(download_tasks)} 个单集", file=sys.stderr)

        # 顺序下载每个文件
        try:
            for task in download_tasks:
                try:
                    success = self.download_file(
                        task['enclosure_url'],
                        task['filepath'],
                        task['episode_title'],
                        task['episode_index']
                    )

                    if success:
                        success_count += 1

                    # 保存单集元数据
                    episode_meta = {
                        "eid": task['episode'].get('eid', ''),
                        "title": task['episode_title'],
                        "filename": task['filename'],
                        "url": task['enclosure_url'],
                        "duration": task['episode'].get('duration', 0),
                        "pub_date": task['episode'].get('pubDate', ''),
                        "description": task['episode'].get('description', ''),
                        "downloaded": task['filepath'].exists()
                    }
                    episode_metadata.append(episode_meta)

                except Exception as e:
                    print(f"\n❌ 任务失败: {task['episode_title'][:40]} - {e}", file=sys.stderr)

        except KeyboardInterrupt:
            print(f"\n⚠️ 用户中断下载", file=sys.stderr)
            raise

        print(f"\n🎉 下载完成！", file=sys.stderr)
        print(f"📊 成功下载: {success_count}/{len(download_tasks)} 个文件", file=sys.stderr)

        return success_count, episode_metadata

    def download_podcast(self, episodes: List[Dict]) -> Dict[str, Any]:
        """下载播客的所有单集"""
        if not episodes:
            print("没有找到单集数据")
            return None

        # 从第一个单集获取播客信息
        first_episode = episodes[0]
        podcast_info = first_episode.get('podcast', {})
        podcast_title = podcast_info.get('title', 'Unknown_Podcast')

        print(f"🎧 开始下载播客: {podcast_title}", file=sys.stderr)

        # 反向排序单集列表（从最早的开始下载）
        episodes_reversed = list(reversed(episodes))

        # 创建下载目录
        download_dir = self.create_download_directory(podcast_title)
        print(f"📁 下载目录: {download_dir.absolute()}", file=sys.stderr)

        total_count = len(episodes_reversed)

        # 多线程下载
        success_count, episode_metadata = self.download_episodes_sequential(
            episodes_reversed, download_dir
        )

        # 保存元数据
        metadata_file = self.save_metadata(podcast_info, episode_metadata, download_dir)

        # 显示下载总结
        print(f"\n📊 下载完成!", file=sys.stderr)
        print(f"📈 成功: {success_count}/{total_count} 个单集", file=sys.stderr)
        print(f"📁 位置: {download_dir.absolute()}", file=sys.stderr)

        # 如果全部下载成功，删除metadata.json文件
        if success_count == total_count and success_count > 0:
            try:
                if metadata_file and metadata_file.exists():
                    metadata_file.unlink()
                    print(f"🗑️  已删除临时元数据文件: {metadata_file.name}", file=sys.stderr)
            except Exception as e:
                print(f"⚠️  删除元数据文件失败: {e}", file=sys.stderr)

        return {
            "podcast_title": podcast_title,
            "download_dir": str(download_dir.absolute()),
            "total_episodes": total_count,
            "downloaded_episodes": success_count,
            "success_rate": f"{(success_count/total_count)*100:.1f}%" if total_count > 0 else "0%"
        }

    def save_only(self, pid: str, max_episodes: Optional[int] = None) -> Dict[str, Any]:
        """仅保存JSON数据，不下载文件"""
        episodes = self.get_all_episodes(pid, max_episodes)

        # 保存JSON数据到data目录
        json_data = {
            "pid": pid,
            "episodes": episodes,
            "fetch_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "total_count": len(episodes)
        }
        data_file = self.save_data_json(pid, json_data)

        return {
            "pid": pid,
            "total_episodes": len(episodes),
            "json_file": str(data_file.absolute()),
            "fetch_time": json_data["fetch_time"]
        }

    def download(self, pid: str, max_episodes: Optional[int] = None) -> Dict[str, Any]:
        """主下载方法"""
        episodes = self.get_all_episodes(pid, max_episodes)

        # 保存JSON数据到data目录
        json_data = {
            "pid": pid,
            "episodes": episodes,
            "fetch_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "total_count": len(episodes)
        }
        self.save_data_json(pid, json_data)

        result = self.download_podcast(episodes)
        return result

    def download_single_episode(self, eid: str) -> Dict[str, Any]:
        """下载单个单集"""
        print(f"🚀 开始获取单集信息: {eid}", file=sys.stderr)

        # 获取单集信息
        result = self.api.get_episode_info(eid)
        if not result["success"]:
            print(f"❌ 获取单集信息失败: {result['error']}", file=sys.stderr)
            return None

        episode_data = result["data"]["data"]

        # 提取单集信息
        episode_title = episode_data.get('title', f'Episode_{eid}')
        enclosure_url = episode_data.get('enclosure', {}).get('url', '')
        is_private_media = episode_data.get('isPrivateMedia', False)

        # 处理付费音频
        if is_private_media:
            print(f"💰 检测到付费内容: {episode_title}", file=sys.stderr)

            # 检查URL是否已经包含private-media域名，如果是则说明已经有权限
            if enclosure_url and "private-media.xyzcdn.net" in enclosure_url:
                print(f"✅ 已有权限，正在下载付费内容", file=sys.stderr)
            else:
                # 尝试获取私有媒体URL
                private_result = self.api.get_private_media_url(eid)

                if private_result["success"]:
                    private_data = private_result["data"]
                    if "data" in private_data and "url" in private_data["data"]:
                        enclosure_url = private_data["data"]["url"]
                        print(f"✅ 获取到付费音频链接，可下载付费内容", file=sys.stderr)
                    else:
                        print(f"❌ 无访问权限，无法下载: {episode_title}", file=sys.stderr)
                        return {
                            "episode_title": episode_title,
                            "success": False,
                            "error": "无访问权限"
                        }
                else:
                    print(f"❌ 无访问权限，无法下载: {episode_title}", file=sys.stderr)
                    return {
                        "episode_title": episode_title,
                        "success": False,
                        "error": "无访问权限"
                    }

        if not enclosure_url:
            print(f"❌ 单集没有音频链接: {episode_title}", file=sys.stderr)
            return None

        # 获取播客信息
        podcast_info = episode_data.get('podcast', {})
        podcast_title = podcast_info.get('title', 'Unknown_Podcast')

        print(f"🎧 播客: {podcast_title}", file=sys.stderr)
        print(f"📻 单集: {episode_title}", file=sys.stderr)

        # 创建下载目录（使用播客名称）
        download_dir = self.create_download_directory(podcast_title)
        print(f"📁 下载目录: {download_dir.absolute()}", file=sys.stderr)

        # 生成文件名
        safe_title = sanitize_filename(episode_title)
        file_extension = get_file_extension(enclosure_url)
        filename = f"{safe_title}{file_extension}"
        filepath = download_dir / filename

        # 下载文件
        print(f"⬇️ 开始下载: {filename}", file=sys.stderr)
        success = self.download_file(enclosure_url, filepath, episode_title, 1)

        if success:
            print(f"✅ 下载完成: {filepath.absolute()}", file=sys.stderr)

            # 保存单集元数据
            episode_metadata = {
                "eid": eid,
                "title": episode_title,
                "filename": filename,
                "url": enclosure_url,
                "duration": episode_data.get('duration', 0),
                "pub_date": episode_data.get('pubDate', ''),
                "description": episode_data.get('description', ''),
                "podcast": podcast_info,
                "download_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "downloaded": True
            }

            # 保存元数据到文件
            metadata_file = download_dir / f"{safe_title}_metadata.json"
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(episode_metadata, f, ensure_ascii=False, indent=2)

            return {
                "episode_title": episode_title,
                "podcast_title": podcast_title,
                "download_dir": str(download_dir.absolute()),
                "filename": filename,
                "filepath": str(filepath.absolute()),
                "success": True
            }
        else:
            print(f"❌ 下载失败: {episode_title}", file=sys.stderr)
            return {
                "episode_title": episode_title,
                "podcast_title": podcast_title,
                "success": False
            }

    def download_from_json(self, json_file: str) -> Dict[str, Any]:
        """从JSON文件下载"""
        data = self.load_from_json(json_file)
        episodes = data.get('episodes', [])

        if not episodes:
            print("JSON文件中没有找到有效的单集数据")
            return None

        result = self.download_podcast(episodes)
        return result
