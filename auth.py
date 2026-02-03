"""
认证管理模块

基于 Refresh Token 的认证方式
用户需要从小宇宙APP或网页抓包获取 refresh_token
"""
import json
import os
from datetime import datetime
from typing import Optional, Dict, Any

try:
    from .api import XiaoyuzhouAPI
    from .config import config
    from .utils import generate_device_id, get_android_device_properties
except ImportError:
    # 如果作为独立模块运行
    from api import XiaoyuzhouAPI
    from config import config
    from utils import generate_device_id, get_android_device_properties


class XiaoyuzhouAuth:
    """小宇宙认证管理类 - 基于 Refresh Token"""

    def __init__(self):
        self.api = XiaoyuzhouAPI()
        self.api.set_auth_handler(self)  # 设置自己为认证处理器
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.device_id: Optional[str] = None
        self.credentials_file = config.credentials_file
        
        # 尝试加载凭据
        self.load_credentials()
        
        # 如果没有device_id，生成一个新的
        if not self.device_id:
            self.device_id = generate_device_id()
            self.api.update_credentials(self.access_token, self.device_id)

    def login_with_refresh_token(self, refresh_token: str, device_id: str) -> Dict[str, Any]:
        """使用 Refresh Token 登录

        Args:
            refresh_token: 从小宇宙APP或网页抓包获取的 refresh_token
            device_id: 与 refresh_token 绑定的 device_id (x-jike-device-id)

        Returns:
            Dict包含 success, access_token, refresh_token, device_id
        """
        if not refresh_token or not refresh_token.strip():
            return {"success": False, "error": "refresh_token 不能为空"}

        if not device_id or not device_id.strip():
            return {"success": False, "error": "device_id 不能为空"}

        self.refresh_token = refresh_token.strip()
        self.device_id = device_id.strip()

        if self.refresh_access_token():
            return {
                "success": True,
                "access_token": self.access_token,
                "refresh_token": self.refresh_token,
                "device_id": self.device_id
            }
        else:
            return {
                "success": False,
                "error": "refresh_token 或 device_id 无效，请重新获取"
            }

    def save_credentials(self, filepath: Optional[str] = None) -> bool:
        """保存认证信息到文件"""
        if not filepath:
            filepath = self.credentials_file

        if self.access_token and self.device_id:
            credentials = {
                "access_token": self.access_token,
                "refresh_token": self.refresh_token,
                "device_id": self.device_id,
                "save_time": datetime.now().isoformat()
            }

            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(credentials, f, ensure_ascii=False, indent=2)

                print(f"✅ 认证信息已保存到 {filepath}")
                return True
            except Exception as e:
                print(f"❌ 保存认证信息失败: {e}")
                return False
        return False

    def load_credentials(self, filepath: Optional[str] = None) -> bool:
        """从文件加载认证信息"""
        if not filepath:
            filepath = self.credentials_file

        try:
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    credentials = json.load(f)

                self.access_token = credentials.get("access_token")
                self.refresh_token = credentials.get("refresh_token")
                self.device_id = credentials.get("device_id")

                if self.access_token and self.device_id:
                    # 更新API实例的认证信息
                    self.api.update_credentials(self.access_token, self.device_id)
                    print(f"✅ 已从 {filepath} 加载认证信息")
                    return True
        except Exception as e:
            print(f"⚠️ 加载认证信息失败: {e}")
        return False

    def interactive_login(self) -> bool:
        """交互式登录 - 使用 Refresh Token"""
        try:
            print("🔐 小宇宙认证")
            print("=" * 50)

            refresh_token = input("请输入 refresh_token: ").strip()
            if not refresh_token:
                print("❌ refresh_token 不能为空")
                return False

            device_id = input("请输入 device_id: ").strip()
            if not device_id:
                print("❌ device_id 不能为空")
                return False

            print("🔑 正在登录...")
            result = self.login_with_refresh_token(refresh_token, device_id)

            if result["success"]:
                print("✅ 登录成功!")
                self.save_credentials()
                return True
            else:
                print(f"❌ 登录失败: {result.get('error', '未知错误')}")
                return False

        except KeyboardInterrupt:
            print("\n⚠️ 登录过程被用户中断")
            return False

    def refresh_access_token(self) -> bool:
        """刷新access_token"""
        if not self.refresh_token:
            print("❌ 没有refresh_token，无法刷新")
            return False

        try:
            import requests
            import urllib3
            from datetime import datetime

            refresh_url = "https://api.xiaoyuzhoufm.com/app_auth_tokens.refresh"

            now = datetime.now()
            local_time = now.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + "+0800"

            refresh_headers = {
                "User-Agent": "okhttp/4.12.0",
                "Accept-Encoding": "gzip",
                "os": "android",
                "os-version": "32",
                "manufacturer": "vivo",
                "model": "V2366GA",
                "resolution": "1080x1920",
                "market": "update",
                "applicationid": "app.podcast.cosmos",
                "app-version": "2.91.0",
                "app-buildno": "1305",
                "x-jike-device-id": self.device_id if self.device_id else "",
                "webviewversion": "101.0.4951.61",
                "app-permissions": "100100",
                "wificonnected": "true",
                "timezone": "Asia/Shanghai",
                "local-time": local_time,
                "x-jike-access-token": self.access_token if self.access_token else "",
                "x-jike-refresh-token": self.refresh_token,
                "x-jike-device-properties": get_android_device_properties(self.device_id),
                "sentry-trace": "00000000000000000000000000000000-0000000000000000-0"
            }

            print("🔄 正在刷新access_token...")
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

            response = requests.get(
                refresh_url,
                headers=refresh_headers,
                timeout=10,
                verify=False
            )

            if response.status_code == 200:
                new_access_token = response.headers.get("x-jike-access-token")
                new_refresh_token = response.headers.get("x-jike-refresh-token")

                if new_access_token:
                    self.access_token = new_access_token
                    if new_refresh_token:
                        self.refresh_token = new_refresh_token

                    self.api.update_credentials(self.access_token, self.device_id)
                    self.save_credentials()

                    print("✅ access_token刷新成功!")
                    return True
                else:
                    print("❌ 刷新响应中未找到新的access_token")
                    return False
            else:
                print(f"❌ token刷新失败: 状态码 {response.status_code}")
                if response.status_code == 401:
                    print("💡 refresh_token可能已过期，请重新登录")
                return False

        except Exception as e:
            print(f"❌ token刷新出现异常: {e}")
            return False

    def verify_token(self) -> bool:
        """验证当前access_token是否有效"""
        if not self.access_token or not self.device_id:
            return False

        try:
            import requests
            import urllib3

            verify_url = "https://api.xiaoyuzhoufm.com/v1/profile/get"
            verify_headers = self.api.get_default_headers()
            verify_headers.update({
                "x-jike-access-token": self.access_token,
                "x-jike-device-id": self.device_id
            })

            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            response = requests.get(verify_url, headers=verify_headers, json={}, timeout=10, verify=False)
            return response.status_code == 200

        except Exception:
            return False

    def ensure_valid_token(self) -> bool:
        """确保有有效的access_token，如果无效则尝试刷新"""
        if not self.access_token:
            return self.refresh_access_token()

        # 验证当前token是否有效
        if self.verify_token():
            return True

        # token无效，尝试刷新
        print("⚠️ access_token已失效，尝试刷新...")
        return self.refresh_access_token()

    def is_authenticated(self) -> bool:
        """检查是否已认证"""
        return bool(self.access_token and self.device_id)

    def ensure_authenticated(self) -> bool:
        """确保有有效的认证信息"""
        # 先尝试加载认证信息
        if not self.is_authenticated():
            self.load_credentials()

        # 如果有认证信息，检查并确保token有效
        if self.is_authenticated():
            if self.ensure_valid_token():
                return True

        # 如果没有认证信息或token刷新失败，提示用户登录
        print("❌ 需要重新登录")
        response = input("是否现在登录? (y/N): ").lower()
        if response == 'y':
            return self.interactive_login()

        return False

    def get_api(self) -> XiaoyuzhouAPI:
        """获取已认证的API实例"""
        if not self.ensure_authenticated():
            print("认证失败")
            return None
        return self.api
