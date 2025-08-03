"""
小宇宙API接口封装
"""
import requests
from typing import Dict, Any, Optional

try:
    from .config import config
except ImportError:
    # 如果作为独立模块运行
    from config import config


class XiaoyuzhouAPI:
    """小宇宙API接口类"""

    def __init__(self, access_token: Optional[str] = None, device_id: Optional[str] = None):
        self.base_url = config.api_base_url
        self.access_token = access_token
        self.device_id = device_id
        self.session = requests.Session()
        self.auth_handler = None  # 将在外部设置

        # 设置基础请求头
        self.session.headers.update({
            'User-Agent': 'okhttp/4.7.2',
            'applicationid': 'app.podcast.cosmos',
            'app-version': '1.6.0',
            'Content-Type': 'application/json'
        })

        # 如果有认证信息，添加到请求头
        if self.access_token:
            self.session.headers['x-jike-access-token'] = self.access_token
        if self.device_id:
            self.session.headers['x-jike-device-id'] = self.device_id

    def set_auth_handler(self, auth_handler):
        """设置认证处理器，用于token刷新"""
        self.auth_handler = auth_handler

    def _make_request_with_retry(self, method: str, url: str, **kwargs) -> requests.Response:
        """发起请求，如果遇到401错误则尝试刷新token后重试"""
        try:
            # 第一次请求
            response = self.session.request(method, url, **kwargs)

            # 如果不是401错误，直接返回
            if response.status_code != 401:
                return response

            # 如果是401错误且有认证处理器，尝试刷新token
            if self.auth_handler and hasattr(self.auth_handler, 'refresh_access_token'):
                print("⚠️ API请求返回401，尝试刷新token...")
                if self.auth_handler.refresh_access_token():
                    # token刷新成功，重新发起请求
                    print("🔄 token刷新成功，重新发起请求...")
                    response = self.session.request(method, url, **kwargs)
                else:
                    print("❌ token刷新失败，请重新登录")

            return response

        except Exception as e:
            # 对于网络错误等异常，直接抛出
            raise e

    def get_default_headers(self) -> Dict[str, str]:
        """获取默认请求头"""
        return {
            "Host": "api.xiaoyuzhoufm.com",
            "App-BuildNo": "1576",
            "OS": "ios",
            "Manufacturer": "Apple",
            "BundleID": "app.podcast.cosmos",
            "abtest-info": '{"old_user_discovery_feed":"enable"}',
            "Accept-Language": "zh-Hant-HK;q=1.0, zh-Hans-CN;q=0.9",
            "Accept": "*/*",
            "Content-Type": "application/json",
            "App-Version": "2.57.1",
            "WifiConnected": "true",
            "OS-Version": "17.4.1",
            "Model": "iPhone14,2",
            "app-permissions": "4",
            "User-Agent": "okhttp/4.7.2"
        }

    def get_sendcode_headers(self) -> Dict[str, str]:
        """获取发送验证码专用请求头"""
        headers = self.get_default_headers()
        headers.update({
            "User-Agent": "Xiaoyuzhou/2.57.1 (build:1576; iOS 17.4.1)",
            "Market": "AppStore",
            "Connection": "keep-alive",
            "Accept-Encoding": "br;q=1.0, gzip;q=0.9, deflate;q=0.8",
            "x-custom-xiaoyuzhou-app-dev": ""
        })
        return headers

    def send_sms_code(self, mobile_phone: str, area_code: str = "+86") -> Dict[str, Any]:
        """发送短信验证码"""
        url = f"{self.base_url}/v1/auth/sendCode"
        headers = self.get_sendcode_headers()

        payload = {
            "mobilePhoneNumber": mobile_phone,
            "areaCode": area_code
        }

        try:
            response = requests.post(url, json=payload, headers=headers)

            print(f"🔍 发送验证码响应状态码: {response.status_code}")
            if response.status_code != 200:
                print(f"🔍 发送验证码响应内容: {response.text}")

            response.raise_for_status()
            return {"success": True, "data": response.json()}
        except requests.RequestException as e:
            print(f"🔍 发送验证码异常: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"🔍 错误响应: {e.response.text}")
            return {"success": False, "error": str(e)}
        except KeyboardInterrupt:
            print("\n⚠️ 发送验证码被用户中断")
            return {"success": False, "error": "用户中断操作"}

    def login_with_sms(self, mobile_phone: str, verify_code: str, area_code: str = "+86") -> Dict[str, Any]:
        """使用SMS验证码登录"""
        url = f"{self.base_url}/v1/auth/loginOrSignUpWithSMS"
        headers = self.get_default_headers()

        payload = {
            "areaCode": area_code,
            "verifyCode": verify_code,
            "mobilePhoneNumber": mobile_phone
        }

        try:
            response = requests.post(url, json=payload, headers=headers)

            print(f"🔍 登录响应状态码: {response.status_code}")

            if response.status_code == 200:
                print(f"🔍 登录响应头: {dict(response.headers)}")

                # 提取认证信息
                access_token = response.headers.get("x-jike-access-token")
                refresh_token = response.headers.get("x-jike-refresh-token")

                if not access_token:
                    print("⚠️ 未收到access token，检查响应头")

                return {
                    "success": True,
                    "data": response.json(),
                    "access_token": access_token,
                    "refresh_token": refresh_token
                }
            else:
                # 处理非200状态码，解析错误信息
                print(f"🔍 登录响应内容: {response.text}")
                try:
                    error_data = response.json()
                    error_msg = error_data.get("toast", error_data.get("message", f"请求失败，状态码: {response.status_code}"))
                    return {"success": False, "error": error_msg}
                except:
                    # 如果响应不是JSON格式，返回原始错误
                    return {"success": False, "error": f"请求失败，状态码: {response.status_code}"}

        except requests.RequestException as e:
            print(f"🔍 登录异常: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"🔍 错误响应: {e.response.text}")
                try:
                    # 尝试解析响应中的错误信息
                    error_data = e.response.json()
                    error_msg = error_data.get("toast", error_data.get("message", str(e)))
                    return {"success": False, "error": error_msg}
                except:
                    pass
            return {"success": False, "error": str(e)}
        except KeyboardInterrupt:
            print("\n⚠️ 登录过程被用户中断")
            return {"success": False, "error": "用户中断操作"}

    def get_episodes_page(self, pid: str, load_more_key: Optional[Dict] = None, limit: int = 25) -> Dict[str, Any]:
        """获取单页单集数据"""
        url = f"{self.base_url}/v1/episode/list"

        if load_more_key:
            payload = {
                "pid": pid,
                "loadMoreKey": load_more_key,
                "order": "desc",
                "limit": limit
            }
        else:
            payload = {
                "pid": pid,
                "limit": limit
            }

        try:
            response = self._make_request_with_retry("POST", url, json=payload)
            response.raise_for_status()
            return {"success": True, "data": response.json()}
        except requests.RequestException as e:
            return {"success": False, "error": str(e)}

    def get_episode_info(self, eid: str) -> Dict[str, Any]:
        """获取单集详细信息"""
        url = f"{self.base_url}/v1/episode/get"

        params = {"eid": eid}

        # 确保使用正确的请求头
        headers = {
            'User-Agent': 'okhttp/4.10.0',
            'Accept-Encoding': 'gzip',
            'Content-Type': 'application/json'
        }

        # 添加认证信息
        if self.access_token:
            headers['x-jike-access-token'] = self.access_token
        if self.device_id:
            headers['x-jike-device-id'] = self.device_id

        try:
            response = self._make_request_with_retry("GET", url, params=params, headers=headers)
            response.raise_for_status()
            return {"success": True, "data": response.json()}
        except requests.RequestException as e:
            return {"success": False, "error": str(e)}

    def get_private_media_url(self, eid: str) -> Dict[str, Any]:
        """获取付费音频的私有媒体URL"""
        url = f"{self.base_url}/v1/private-media/get"
        
        params = {"eid": eid}
        
        # 确保使用正确的请求头
        headers = {
            'User-Agent': 'okhttp/4.10.0',
            'Accept-Encoding': 'gzip',
            'Content-Type': 'application/json'
        }
        
        # 添加认证信息
        if self.access_token:
            headers['x-jike-access-token'] = self.access_token
        if self.device_id:
            headers['x-jike-device-id'] = self.device_id
        
        try:
            response = self._make_request_with_retry("GET", url, params=params, headers=headers)
            response.raise_for_status()
            return {"success": True, "data": response.json()}
        except requests.RequestException as e:
            return {"success": False, "error": str(e)}

    def update_credentials(self, access_token: str, device_id: str):
        """更新认证信息"""
        self.access_token = access_token
        self.device_id = device_id

        self.session.headers.update({
            'x-jike-access-token': access_token,
            'x-jike-device-id': device_id
        })
