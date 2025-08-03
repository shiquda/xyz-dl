# 🎧 小宇宙播客下载器 (xyz-dl)

一个简单易用的小宇宙播客下载工具，支持批量下载播客专辑或单集。

## ✨ 主要功能

- 🔐 **手机号登录** - 支持小宇宙账号登录
- 📻 **播客下载** - 下载整个播客的所有集数  
- 🎵 **单集下载** - 下载指定的单个播客集数
- 📊 **限制下载** - 可设置最大下载集数
- 📈 **下载进度** - 实时显示下载进度条
- 💾 **数据保存** - 可选择仅保存元数据，不下载文件
- 📁 **自定义目录** - 支持指定下载路径

## 🚀 快速开始

### 环境要求

- Python 3.13+
- 依赖包：`requests`, `tqdm`

### 使用

```bash
# 克隆项目
git clone https://github.com/shiquda/xyz-dl.git
cd xyz-dl

# 安装依赖
uv sync

```

### 基本使用

#### 1️⃣ 交互式模式（推荐新手）

```bash
python main.py
```

程序会引导你完成登录和下载设置。

#### 2️⃣ 命令行模式

```bash
# 首次使用需要登录，可使用交互式模式进行设置
python main.py

# 下载整个播客
python main.py 682c566cc7c5f17595635a2c

# 使用播客URL下载
python main.py https://www.xiaoyuzhoufm.com/podcast/6603ea352d9eae5d0a5f9151

# 下载单集
python main.py https://www.xiaoyuzhoufm.com/episode/6888a0148e06fe8de74811af

# 限制下载数量
python main.py 682c566cc7c5f17595635a2c --max-episodes 10

# 指定下载目录
python main.py 682c566cc7c5f17595635a2c --output /path/to/download

# 仅保存元数据，不下载文件
python main.py 682c566cc7c5f17595635a2c --save-only
```

## 📖 详细用法

### 获取播客专辑/单集URL

可从APP>分享>复制链接中获取。例如：

- 播客专辑页面：`https://www.xiaoyuzhoufm.com/podcast/6013f9f58e2f7ee375cf4216`
- 播客单集页面：`https://www.xiaoyuzhoufm.com/episode/688c67368e06fe8de7ca55f8`

### 命令行参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `--login` | 手机号登录 | `python main.py --login` |
| `--max-episodes` | 最大下载集数 | `--max-episodes 50` |
| `--output, -o` | 下载目录 | `--output /path/to/download` |
| `--save-only` | 仅保存数据，不下载 | `--save-only` |
| `--from-json` | 从JSON文件下载 | `--from-json data/podcast.json` |

### 配置文件

项目使用 `xyz-config.json` 进行配置：

```json
{
  "download": {
    "download_dir": "download",  // 默认下载目录
    "timeout": 60            // 下载超时时间
  }
}
```

## 📁 项目结构

```
xyz-dl/
├── main.py          # 主程序入口
├── auth.py          # 认证模块
├── downloader.py    # 下载核心
├── api.py           # API接口
├── config.py        # 配置管理
├── utils.py         # 工具函数
├── xyz-config.json      # 配置文件
└── pyproject.toml   # 项目配置
```

## ⚠️ 注意事项

- ⚠️ 本工具为个人离线学习和收听提供便利，在使用时请遵守小宇宙平台的相关规定，切勿在互联网上公开传播。
- 首次使用需要手机号登录验证
- 认证信息会自动保存，无需重复登录

## 🐛 常见问题

**Q: 登录失败怎么办？**  
A: 确保手机号格式正确，验证码输入及时，网络连接正常。

**Q: 找不到播客ID？**  
A: 从小宇宙网页URL中复制，或在手机APP>分享中获取播客专辑/单集URL。

**Q: 下载失败？**  
A: 检查网络连接，确认播客是否公开访问，重试登录。

**Q: 为什么下载的文件大小只有0.01MB？**  
A: 请检查登录账号对相关内容的访问权限，若无购买则为0.01MB。

## 📄 许可证

本项目仅供学习交流使用，请遵守相关法律法规和平台条款。

---

💡 **提示**：如果你是第一次使用，推荐先运行 `python main.py` 进入交互式模式，它会引导你完成所有设置。
