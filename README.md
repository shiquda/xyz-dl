# 小宇宙播客下载器 (xyz-dl)

> [!WARNING]
> **不再建议使用。** 已有用户报告使用本工具可能触发小宇宙账号风控或封禁风险。请不要在重要账号上使用，也不要进行批量、高频或自动化下载。项目仅保留作研究与代码参考，使用者需自行承担账号风险。

一个简单易用的小宇宙播客下载工具，支持批量下载播客专辑或单集。

## 主要功能

- **Token 认证** - 使用 refresh_token 和 device_id 认证
- **播客下载** - 下载整个播客的所有集数
- **单集下载** - 下载指定的单个播客集数
- **数据保存** - 可选择仅保存元数据，不下载文件
- **字幕下载** - 支持下载单集字幕（`--with-subtitles`）
- **自定义目录** - 支持指定下载路径

## 快速开始

### 环境要求

- Python 3.13+

### 安装

方式一：使用 UV Tool 安装到本地（推荐）

```bash
uv tool install --from "git+https://github.com/shiquda/xyz-dl.git" xyz-dl
xyz-dl --help
```

方式二：本地开发安装（uv）

```bash
# 克隆项目
git clone https://github.com/shiquda/xyz-dl.git
cd xyz-dl

# 安装依赖
uv sync

# 运行
uv run xyz-dl --help
```

## 使用方法

### 首次使用

首次使用需要登录认证：

```bash
# 交互式登录（推荐）
xyz-dl --login
# 按提示输入 refresh_token 和 device_id

# 或命令行直接指定
xyz-dl --refresh-token <your_token> --device-id <your_device_id>
```

认证信息会自动保存到 `credentials.json`，后续无需重复登录。

### 下载播客

```bash
# 下载整个播客
xyz-dl 682c566cc7c5f17595635a2c

# 使用播客URL下载
xyz-dl https://www.xiaoyuzhoufm.com/podcast/6603ea352d9eae5d0a5f9151

# 下载单集
xyz-dl https://www.xiaoyuzhoufm.com/episode/6888a0148e06fe8de74811af

# 限制下载数量
xyz-dl 682c566cc7c5f17595635a2c --max-episodes 10

# 指定下载目录
xyz-dl 682c566cc7c5f17595635a2c --output /path/to/download

# 仅保存元数据，不下载文件
xyz-dl 682c566cc7c5f17595635a2c --save-only

# 仅保存元数据和字幕，不下载音频
xyz-dl 682c566cc7c5f17595635a2c --save-only --subtitles

# 兼容旧参数写法
xyz-dl 682c566cc7c5f17595635a2c --save-only --with-subtitles

# 仅在调试或特殊网络环境下临时禁用 HTTPS 证书校验
xyz-dl 682c566cc7c5f17595635a2c --insecure
```

### 获取播客链接

- 播客专辑页面：`https://www.xiaoyuzhoufm.com/podcast/<podcast_id>`
- 播客单集页面：`https://www.xiaoyuzhoufm.com/episode/<episode_id>`

可从 APP > 分享 > 复制链接 中获取。

## 命令行参数

| 参数                | 说明                                | 示例                              |
|--------------------|-----------------------------------|---------------------------------|
| `--login`          | 交互式登录                             | `xyz-dl --login`                |
| `--refresh-token`  | 指定 refresh_token（需配合 --device-id） | `--refresh-token <token>`       |
| `--device-id`      | 指定 device_id                      | `--device-id <device_id>`       |
| `--max-episodes`   | 最大下载集数                            | `--max-episodes 50`             |
| `--output, -o`     | 下载目录                              | `--output /path/to/download`    |
| `--save-only`      | 仅保存数据，不下载                         | `--save-only`                   |
| `--from-json`      | 从JSON文件下载                         | `--from-json data/podcast.json` |
| `--subtitles [FORMAT]` | 下载字幕，支持 `txt`/`srt`               | `--subtitles srt`               |
| `--with-subtitles` | 兼容旧参数，等同于 `--subtitles txt`      | `--save-only --with-subtitles`  |
| `--insecure`       | 临时禁用 HTTPS 证书校验（不安全）           | `--insecure`                    |

## 项目结构

```
xyz-dl/
├── main.py          # 主程序入口
├── auth.py          # 认证模块
├── downloader.py    # 下载核心
├── api.py           # API接口
├── config.py        # 配置管理
├── utils.py         # 工具函数
├── xyz-config.json  # 配置文件
└── pyproject.toml   # 项目配置
```

## 注意事项

- **API 安全建议**：当前 `device-id` 与请求 Headers 不一致是显著的机器人特征，存在被识别的风险。建议有能力的用户通过实机抓包获取本机的 `refresh_token` 与 `device-id`，并同步修改 `api.py` 中的 `get_default_headers` 方法以匹配对应的 Headers 字段，来避免可能的风控。
- **TLS 证书校验**：默认会验证 HTTPS 证书，仅在显式传入 `--insecure` 时才会临时跳过校验。该模式不安全，可能导致 token 泄露或下载内容被篡改。
- 本工具为个人离线学习和收听提供便利，在使用时请遵守小宇宙平台的相关规定，切勿在互联网上公开传播，禁止用于商业目的。
- 认证信息（`credentials.json`）包含个人敏感信息，请勿分享给他人。
- 下载的文件仅供个人使用，请尊重版权。

## 常见问题

**Q: 登录失败怎么办？**  
A: 请检查 refresh_token 和 device_id 是否正确，两者必须匹配。

**Q: 找不到播客ID？**  
A: 从小宇宙网页URL中复制，或在手机APP>分享中获取播客专辑/单集URL。

**Q: 下载失败？**  
A: 检查网络连接，确认播客是否公开访问，尝试重新登录。

**Q: 为什么下载的文件大小只有0.01MB？**  
A: 请检查登录账号对相关内容的访问权限，若无购买则为0.01MB。

## 许可证

AGPL-3.0

> 本项目仅供学习交流使用，在使用时请遵守所在地区的相关法律法规和平台条款。

## 致谢

- <https://github.com/ultrazg/xyz>
- <https://github.com/DIYgod/RSSHub>
