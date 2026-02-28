"""
下载器模块
"""
import sys
import time
import random
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Any
import requests
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from tqdm import tqdm

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    from .auth import XiaoyuzhouAuth
    from .config import config
    from .utils import sanitize_filename, format_size, get_file_extension, create_directory, print_table, save_metadata_files, transcript_to_srt
except ImportError:
    # 如果作为独立模块运行
    from auth import XiaoyuzhouAuth
    from config import config
    from utils import sanitize_filename, format_size, get_file_extension, create_directory, print_table, save_metadata_files, transcript_to_srt


class XiaoyuzhouDownloader:
    """小宇宙播客下载器"""

    def __init__(self, auth: Optional[XiaoyuzhouAuth] = None, save_metadata: bool = True):
        self.auth = auth or XiaoyuzhouAuth()
        self.save_metadata_enabled = save_metadata

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

        session.verify = False

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

    def download_subtitle(self, transcript_url: str, filepath: Path, subtitle_format: str = 'txt') -> bool:
        """下载字幕文件，支持 txt 和 srt 格式"""
        if not transcript_url:
            return False
        headers = {
            "Host": transcript_url.split('/')[2],
            "Accept": "application/json",
            "User-Agent": "Xiaoyuzhou/2.99.1(android 28)"
        }
        try:
            response = self.download_session.get(transcript_url, headers=headers, timeout=config.get('download.timeout', 60))
            response.raise_for_status()
            try:
                data = response.json()
            except json.JSONDecodeError:
                print(f"❌ 字幕不是有效的JSON格式", file=sys.stderr)
                return False

            # 统一提取列表
            items: list = []
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                for key in ['data', 'segments', 'body', 'content', 'items']:
                    if key in data and isinstance(data[key], list):
                        items = data[key]
                        break

            if subtitle_format == 'srt':
                content = transcript_to_srt(items)
                out_path = filepath.with_suffix('.srt')
            else:
                content = "\n".join(str(item['text']) for item in items if isinstance(item, dict) and 'text' in item)
                out_path = filepath

            with open(out_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"📝 字幕下载成功: {out_path.name}", file=sys.stderr)
            return True
        except Exception as e:
            print(f"❌ 字幕下载失败: {e}", file=sys.stderr)
            return False

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

    def save_data_json(self, pid: str, episodes_data: Dict[str, Any], podcast_title: Optional[str] = None) -> Path:
        """保存JSON数据到播客目录，以ID命名"""
        if not podcast_title:
            podcast_title = "Unknown_Podcast"
            
        safe_title = sanitize_filename(podcast_title)
        data_dir = config.download_dir / safe_title
            
        data_dir = create_directory(data_dir)
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

    def download_episodes_sequential(
        self,
        episodes: List[Dict],
        download_dir: Path,
        subtitle_format: Optional[str] = None,
        download_audio: bool = True
    ) -> tuple:
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
            media_id = episode.get('media', {}).get('id', '')

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

            if download_audio and not enclosure_url:
                print(f"  ⚠️  [{i:03d}] 跳过: 无音频链接 - {episode_title}")
                continue

            # 生成安全的文件名
            safe_title = sanitize_filename(episode_title)
            file_extension = get_file_extension(enclosure_url)
            filename = f"{i:03d}. {safe_title}{file_extension}"
            filepath = download_dir / filename
            subtitle_filename = f"{safe_title}.{subtitle_format or 'txt'}"
            subtitle_filepath = download_dir / subtitle_filename

            download_tasks.append({
                'episode': episode,
                'episode_title': episode_title,
                'enclosure_url': enclosure_url,
                'filepath': filepath,
                'filename': filename,
                'episode_index': i,
                'is_private_media': is_private_media,
                'eid': eid,
                'media_id': media_id,
                'subtitle_filepath': subtitle_filepath
            })

        print(f"🚀 开始顺序下载 {len(download_tasks)} 个单集", file=sys.stderr)

        # 顺序下载每个文件
        try:
            for task in download_tasks:
                try:
                    if download_audio:
                        success = self.download_file(
                            task['enclosure_url'],
                            task['filepath'],
                            task['episode_title'],
                            task['episode_index']
                        )
                    else:
                        success = True

                    if success:
                        success_count += 1
                        
                        # 下载字幕
                        if subtitle_format:
                            # 检查字幕是否已存在
                            if task['subtitle_filepath'].exists():
                                print(f"  ⏩ 跳过已存在的字幕: {task['subtitle_filepath'].name}", file=sys.stderr)
                            else:
                                # 获取字幕URL
                                transcript_result = self.api.get_episode_transcript(task['eid'], task['media_id'])
                                if transcript_result["success"]:
                                    transcript_url = None
                                    api_data = transcript_result.get("data")
                                    if api_data and isinstance(api_data, dict):
                                        inner_data = api_data.get("data")
                                        if inner_data and isinstance(inner_data, dict):
                                            transcript_url = inner_data.get("transcriptUrl")
                                            
                                    if transcript_url:
                                        self.download_subtitle(transcript_url, task['subtitle_filepath'], subtitle_format)
                                    else:
                                        print(f"  ⚠️  未找到字幕: {task['episode_title'][:40]}", file=sys.stderr)
                                else:
                                    print(f"  ⚠️  获取字幕信息失败: {task['episode_title'][:40]}", file=sys.stderr)

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

    def download_podcast(
        self,
        episodes: List[Dict],
        subtitle_format: Optional[str] = None,
        download_audio: bool = True
    ) -> Dict[str, Any]:
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
            episodes_reversed,
            download_dir,
            subtitle_format=subtitle_format,
            download_audio=download_audio
        )

        # 保存元数据
        metadata_file = None
        if self.save_metadata_enabled:
            metadata_file = self.save_metadata(podcast_info, episode_metadata, download_dir)
            # 保存详细元数据文件 (JSON 和 Markdown)
            save_metadata_files(podcast_info, download_dir, "podcast_metadata")

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

    def save_only(self, pid: str, max_episodes: Optional[int] = None, subtitle_format: Optional[str] = None) -> Dict[str, Any]:
        """仅保存JSON数据，不下载文件"""
        episodes = self.get_all_episodes(pid, max_episodes)
        
        podcast_title = None
        if episodes:
            podcast_title = episodes[0].get('podcast', {}).get('title')

        json_data = {
            "pid": pid,
            "episodes": episodes,
            "fetch_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "total_count": len(episodes)
        }
        data_file = None
        if self.save_metadata_enabled:
            data_file = self.save_data_json(pid, json_data, podcast_title)
        
        # 如果需要下载字幕
        if subtitle_format and episodes:
            print(f"📝 正在下载字幕...", file=sys.stderr)
            # 复用download_podcast的逻辑，但在download_episodes_sequential中如果不传enclosure_url或者修改逻辑...
            # 其实可以直接调用download_podcast，但是需要一种方式告诉它只下载字幕不下载音频
            # 但是download_podcast目前是下载音频的。
            
            # 方案：手动调用download_episodes_sequential，但是这会下载音频。
            # 或者修改download_episodes_sequential，增加audio_download=False？
            
            # 简单起见，我直接在这里遍历下载字幕
            download_dir = self.create_download_directory(podcast_title)
            
            count = 0
            for i, episode in enumerate(episodes, 1):
                episode_title = episode.get('title', f'Episode_{i}')
                eid = episode.get('eid')
                media_id = episode.get('media', {}).get('id')
                
                safe_title = sanitize_filename(episode_title)
                subtitle_filename = f"{safe_title}.{subtitle_format or 'txt'}"
                subtitle_filepath = download_dir / subtitle_filename

                # 检查字幕是否已存在
                if subtitle_filepath.exists():
                    print(f"⏩ 跳过已存在的字幕: {subtitle_filename}", file=sys.stderr)
                    continue

                # 在下载之间添加随机间隔
                if count > 0:
                    delay = random.uniform(8, 15)
                    print(f"⏳ 等待 {delay:.1f} 秒以避免频率过快...", file=sys.stderr)
                    time.sleep(delay)
                
                transcript_result = self.api.get_episode_transcript(eid, media_id)
                if transcript_result["success"]:
                    transcript_url = None
                    api_data = transcript_result.get("data")
                    if api_data and isinstance(api_data, dict):
                        inner_data = api_data.get("data")
                        if inner_data and isinstance(inner_data, dict):
                            transcript_url = inner_data.get("transcriptUrl")

                    if transcript_url:
                        if self.download_subtitle(transcript_url, subtitle_filepath, subtitle_format):
                            count += 1
            
            print(f"📝 已下载 {count} 个字幕文件", file=sys.stderr)

        return {
            "pid": pid,
            "total_episodes": len(episodes),
            "json_file": str(data_file.absolute()) if data_file else None,
            "fetch_time": json_data["fetch_time"]
        }

    def download(self, pid: str, max_episodes: Optional[int] = None, subtitle_format: Optional[str] = None) -> Dict[str, Any]:
        """主下载方法"""
        episodes = self.get_all_episodes(pid, max_episodes)
        
        podcast_title = None
        if episodes:
            podcast_title = episodes[0].get('podcast', {}).get('title')

        # 保存JSON数据到播客目录
        json_data = {
            "pid": pid,
            "episodes": episodes,
            "fetch_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "total_count": len(episodes)
        }
        self.save_data_json(pid, json_data, podcast_title)

        result = self.download_podcast(episodes, subtitle_format=subtitle_format)
        return result

    def download_single_episode(self, eid: str, save_only: bool = False, subtitle_format: Optional[str] = None) -> Dict[str, Any]:
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
        media_id = episode_data.get('media', {}).get('id', '')

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
        
        if not save_only:
            print(f"📁 下载目录: {download_dir.absolute()}", file=sys.stderr)

        # 生成文件名
        safe_title = sanitize_filename(episode_title)
        file_extension = get_file_extension(enclosure_url)
        filename = f"{safe_title}{file_extension}"
        filepath = download_dir / filename
        
        # 字幕文件名
        subtitle_filename = f"{safe_title}.{subtitle_format or 'txt'}"
        subtitle_filepath = download_dir / subtitle_filename

        success = True
        if not save_only:
            # 下载文件
            print(f"⬇️ 开始下载: {filename}", file=sys.stderr)
            success = self.download_file(enclosure_url, filepath, episode_title, 1)
        else:
            print(f"💾 仅保存元数据", file=sys.stderr)
            
        # 如果下载成功（或者只是保存元数据），尝试下载字幕
        if success and subtitle_format:
            # 检查字幕是否已存在
            if subtitle_filepath.exists():
                print(f"⏩ 跳过已存在的字幕: {subtitle_filename}", file=sys.stderr)
            else:
                # 获取字幕URL
                transcript_result = self.api.get_episode_transcript(eid, media_id)
                if transcript_result["success"]:
                    transcript_url = None
                    api_data = transcript_result.get("data")
                    if api_data and isinstance(api_data, dict):
                        inner_data = api_data.get("data")
                        if inner_data and isinstance(inner_data, dict):
                            transcript_url = inner_data.get("transcriptUrl")

                    if transcript_url:
                        self.download_subtitle(transcript_url, subtitle_filepath, subtitle_format)
                    else:
                        print(f"  ⚠️  未找到字幕", file=sys.stderr)
                else:
                    print(f"  ⚠️  获取字幕信息失败", file=sys.stderr)

        if success:
            if not save_only:
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
                "downloaded": not save_only
            }

            if self.save_metadata_enabled:
                # 保存元数据到文件
                metadata_file = download_dir / f"{safe_title}_metadata.json"
                with open(metadata_file, 'w', encoding='utf-8') as f:
                    json.dump(episode_metadata, f, ensure_ascii=False, indent=2)

                # 保存详细元数据文件 (JSON 和 Markdown)
                save_metadata_files(episode_metadata, download_dir, f"{safe_title}_metadata")

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

    def download_from_json(
        self,
        json_file: str,
        subtitle_format: Optional[str] = None,
        download_audio: bool = True
    ) -> Dict[str, Any]:
        """从JSON文件下载"""
        data = self.load_from_json(json_file)
        episodes = data.get('episodes', [])

        if not episodes:
            print("JSON文件中没有找到有效的单集数据")
            return None

        result = self.download_podcast(
            episodes,
            subtitle_format=subtitle_format,
            download_audio=download_audio
        )
        return result

    def display_podcast_info(self, podcast_info: Dict[str, Any]):
        """显示播客信息表格"""
        headers = ["属性", "内容"]
        rows = [
            ["播客名称", podcast_info.get("title", "N/A")],
            ["作者", podcast_info.get("author", "N/A")],
            ["单集总数", podcast_info.get("episodeCount", "N/A")],
            ["订阅人数", podcast_info.get("subscriptionCount", "N/A")],
            ["简介", podcast_info.get("brief", "N/A")]
        ]
        print("\n🎧 播客详细信息:")
        print_table(headers, rows)

    def display_host_info(self, podcasters: List[Dict[str, Any]]):
        """显示主播信息表格"""
        if not podcasters:
            print("\n🎙️ 未找到主播信息")
            return
        
        headers = ["昵称", "IP属地", "个人简介"]
        rows = []
        for host in podcasters:
            rows.append([
                host.get("nickname", "N/A"),
                host.get("ipLoc", "N/A"),
                host.get("bio", "N/A")
            ])
        print("\n🎙️ 主播/嘉宾信息:")
        print_table(headers, rows)

    def display_episode_info(self, episode_data: Dict[str, Any]):
        """显示单集信息表格"""
        headers = ["属性", "内容"]
        duration_min = episode_data.get("duration", 0) // 60
        rows = [
            ["单集标题", episode_data.get("title", "N/A")],
            ["时长", f"{duration_min} 分钟"],
            ["发布日期", episode_data.get("pubDate", "N/A")],
            ["播放量", episode_data.get("playCount", "N/A")],
            ["点赞数", episode_data.get("clapCount", "N/A")],
            ["评论数", episode_data.get("commentCount", "N/A")]
        ]
        print("\n📻 单集详细信息:")
        print_table(headers, rows)

    def display_info(self, input_type: str, extracted_id: str) -> bool:
        """根据输入类型显示详细信息"""
        if input_type == "episode":
            result = self.api.get_episode_info(extracted_id)
            if not result["success"]:
                print(f"❌ 获取单集信息失败: {result['error']}")
                return False
            
            data = result["data"]["data"]
            self.display_episode_info(data)
            self.display_podcast_info(data.get("podcast", {}))
            self.display_host_info(data.get("podcast", {}).get("podcasters", []))
            return True
        
        elif input_type == "podcast":
            # 我们需要先获取播客的第一个单集来获取播客详情
            # 或者如果有专门的播客详情接口更好
            # 目前 XiaoyuzhouAPI 只有 get_episodes_page
            result = self.api.get_episodes_page(extracted_id, limit=1)
            if not result["success"]:
                print(f"❌ 获取播客信息失败: {result['error']}")
                return False
            
            episodes = result["data"].get("data", [])
            if not episodes:
                print("❌ 未找到该播客的任何信息")
                return False
            
            podcast_info = episodes[0].get("podcast", {})
            self.display_podcast_info(podcast_info)
            self.display_host_info(podcast_info.get("podcasters", []))
            return True
        
        return False
