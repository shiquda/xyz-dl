"""
配置管理模块
"""
import os
import json
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime


class Config:
    """配置管理类"""

    def __init__(self, config_dir: str = "."):
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(exist_ok=True)

        # 默认配置
        self.default_config = {
            "api": {
                "base_url": "https://api.xiaoyuzhoufm.com",
                "timeout": 30,
                "max_retries": 3
            },
            "download": {
                "chunk_size": 8192,
                "download_dir": "download",
                "max_retries": 3,
                "retry_delay": 2,
                "timeout": 60
            },
            "auth": {
                "credentials_file": "credentials.json",
                "auto_refresh": True
            }
        }

        self.config_file = self.config_dir / "xyz-config.json"
        self.load_config()

    def load_config(self):
        """加载配置文件"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)

                # 合并用户配置和默认配置
                self.config = self._merge_config(self.default_config, user_config)
            except Exception as e:
                print(f"加载配置文件失败: {e}")
                raise
        else:
            self.config = self.default_config.copy()
            self.save_config()

    def save_config(self):
        """保存配置文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存配置文件失败: {e}")
            raise

    def _merge_config(self, default: Dict, user: Dict) -> Dict:
        """递归合并配置"""
        result = default.copy()
        for key, value in user.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_config(result[key], value)
            else:
                result[key] = value
        return result

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值，支持点分割的键名"""
        keys = key.split('.')
        value = self.config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def set(self, key: str, value: Any):
        """设置配置值，支持点分割的键名"""
        keys = key.split('.')
        config = self.config

        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]

        config[keys[-1]] = value
        self.save_config()

    @property
    def api_base_url(self) -> str:
        return self.get('api.base_url')

    def set_download_dir(self, download_dir: str):
        """动态设置下载目录"""
        self._custom_download_dir = Path(download_dir)

    @property
    def download_dir(self) -> Path:
        # 如果设置了自定义下载目录，使用自定义的
        if hasattr(self, '_custom_download_dir'):
            return self._custom_download_dir
        return Path(self.get('download.download_dir'))

    @property
    def api_timeout(self) -> int:
        return self.get('api.timeout')

    @property
    def credentials_file(self) -> Path:
        return self.config_dir / self.get('auth.credentials_file')


# 全局配置实例
config = Config()
