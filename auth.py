"""
认证管理模块
"""
import json
import os
from datetime import datetime
from typing import Optional, Dict, Any

try:
    from .api import XiaoyuzhouAPI
    from .config import config
    from .utils import generate_device_id, validate_phone_number, validate_area_code
except ImportError:
    # 如果作为独立模块运行
    from api import XiaoyuzhouAPI
    from config import config
    from utils import generate_device_id, validate_phone_number, validate_area_code


class XiaoyuzhouAuth:
    """小宇宙认证管理类"""

    def __init__(self):
        self.api = XiaoyuzhouAPI()
        self.api.set_auth_handler(self)  # 设置自己为认证处理器
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.device_id: Optional[str] = None
        self.credentials_file = config.credentials_file

    def send_sms_code(self, mobile_phone: str, area_code: str = "+86") -> Dict[str, Any]:
        """发送短信验证码"""
        # 验证输入
        if not validate_phone_number(mobile_phone):
            return {"success": False, "error": "手机号格式不正确"}

        if not validate_area_code(area_code):
            return {"success": False, "error": "区号格式不正确"}

        return self.api.send_sms_code(mobile_phone, area_code)

    def login_with_sms(self, mobile_phone: str, verify_code: str, area_code: str = "+86") -> Dict[str, Any]:
        """使用SMS验证码登录"""
        # 验证输入
        if not validate_phone_number(mobile_phone):
            return {"success": False, "error": "手机号格式不正确"}

        if not verify_code.strip():
            return {"success": False, "error": "验证码不能为空"}

        if not validate_area_code(area_code):
            return {"success": False, "error": "区号格式不正确"}

        result = self.api.login_with_sms(mobile_phone, verify_code, area_code)

        if result["success"]:
            # 保存认证信息
            self.access_token = result["access_token"]
            self.refresh_token = result["refresh_token"]

            if not self.device_id:
                self.device_id = generate_device_id()

            # 更新API实例的认证信息
            self.api.update_credentials(self.access_token, self.device_id)

            # 添加device_id到返回结果
            result["device_id"] = self.device_id

        return result

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
        """交互式登录"""
        try:
            print("🔐 开始手机号登录流程")

            # 输入手机号
            mobile_phone = input("请输入手机号: ").strip()
            if not mobile_phone:
                print("❌ 手机号不能为空")
                return False

            if not validate_phone_number(mobile_phone):
                print("❌ 手机号格式不正确")
                return False

            area_code = input("请输入区号 (默认 +86): ").strip()
            if not area_code:
                area_code = "+86"

            if not validate_area_code(area_code):
                print("❌ 区号格式不正确")
                return False

            # 发送验证码
            print("📱 正在发送验证码...")
            sms_result = self.send_sms_code(mobile_phone, area_code)

            if not sms_result["success"]:
                print(f"❌ 发送验证码失败: {sms_result['error']}")
                return False

            print("✅ 验证码已发送")

            # 验证码重试机制 - 最多尝试3次
            max_attempts = 3
            for attempt in range(max_attempts):
                # 输入验证码
                if attempt > 0:
                    print(f"\n📱 剩余 {max_attempts - attempt} 次尝试机会")
                
                verify_code = input("请输入验证码: ").strip()
                if not verify_code:
                    print("❌ 验证码不能为空")
                    continue

                # 登录
                print("🔑 正在登录...")
                login_result = self.login_with_sms(mobile_phone, verify_code, area_code)

                if login_result["success"]:
                    print("✅ 登录成功!")
                    self.save_credentials()
                    return True
                else:
                    error_msg = login_result.get('error', '未知错误')
                    print(f"❌ 登录失败: {error_msg}")
                    
                    # 检查是否是验证码错误
                    if "验证码" in error_msg and attempt < max_attempts - 1:
                        print("💡 请检查验证码是否正确，或重新获取验证码")
                        
                        # 询问是否重新发送验证码
                        resend = input("是否重新发送验证码? (y/N): ").lower().strip()
                        if resend == 'y':
                            print("📱 正在重新发送验证码...")
                            sms_result = self.send_sms_code(mobile_phone, area_code)
                            if sms_result["success"]:
                                print("✅ 验证码已重新发送")
                            else:
                                print(f"❌ 重新发送失败: {sms_result['error']}")
                                return False
                        continue
                    else:
                        # 非验证码错误或已达到最大尝试次数
                        return False

            print("❌ 验证码尝试次数已用完，登录失败")
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

            refresh_url = "https://api.xiaoyuzhoufm.com/app_auth_tokens.refresh"
            refresh_headers = {
                "User-Agent": "okhttp/4.10.0",
                "Accept-Encoding": "gzip",
                "Content-Type": "application/json",
                "x-jike-refresh-token": self.refresh_token
            }

            print("🔄 正在刷新access_token...")
            response = requests.post(
                refresh_url,
                headers=refresh_headers,
                json={},
                timeout=10
            )

            if response.status_code == 200:
                refresh_data = response.json()
                new_access_token = refresh_data.get("x-jike-access-token")
                new_refresh_token = refresh_data.get("x-jike-refresh-token")

                if new_access_token:
                    self.access_token = new_access_token
                    if new_refresh_token:
                        self.refresh_token = new_refresh_token

                    # 更新API实例的认证信息
                    self.api.update_credentials(self.access_token, self.device_id)

                    # 保存新的认证信息
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

            verify_url = "https://api.xiaoyuzhoufm.com/v1/profile/get"
            verify_headers = {
                "User-Agent": "okhttp/4.10.0",
                "Accept-Encoding": "gzip",
                "Content-Type": "application/json",
                "x-jike-access-token": self.access_token,
                "x-jike-device-id": self.device_id
            }

            response = requests.get(verify_url, headers=verify_headers, json={}, timeout=10)
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
