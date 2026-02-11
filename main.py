#!/usr/bin/env python3
"""
小宇宙播客下载器

使用示例:
  python main.py                                               # 交互式模式
  python main.py --login                                       # 交互式输入 refresh_token 登录
  python main.py --refresh-token <token>                       # 命令行传入 refresh_token 登录
  python main.py 682c566cc7c5f17595635a2c                    # 基本下载
  python main.py https://www.xiaoyuzhoufm.com/podcast/6603ea352d9eae5d0a5f9151  # 播客URL下载
  python main.py https://www.xiaoyuzhoufm.com/episode/6888a0148e06fe8de74811af  # 单集URL下载
  python main.py 682c566cc7c5f17595635a2c --max-episodes 50  # 限制下载数量
  python main.py 682c566cc7c5f17595635a2c --output /path/to/download  # 指定下载目录
  python main.py 682c566cc7c5f17595635a2c --save-only        # 仅保存JSON，不下载
  python main.py --from-json download/PodcastName/682c566cc7c5f17595635a2c.json  # 从JSON文件下载

"""
import argparse
import json
import sys
from pathlib import Path

try:
    from auth import XiaoyuzhouAuth
    from downloader import XiaoyuzhouDownloader
    from config import config
    from utils import detect_input_type, is_valid_podcast_id
except ImportError as e:
    print(f"❌ 模块导入失败: {e}")
    print("请确保所有必要的模块文件都在同一目录下")
    sys.exit(1)


def create_parser() -> argparse.ArgumentParser:
    """创建命令行参数解析器"""
    parser = argparse.ArgumentParser(
        description='🎧 小宇宙播客下载器',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python main.py                                                                # 交互式模式
  python main.py --login                                                        # 交互式输入 refresh_token 登录
  python main.py --refresh-token <token>                                        # 命令行传入 refresh_token 登录
  python main.py 682c566cc7c5f17595635a2c                                       # 基本下载
  python main.py https://www.xiaoyuzhoufm.com/podcast/6603ea352d9eae5d0a5f9151  # 播客URL下载
  python main.py https://www.xiaoyuzhoufm.com/episode/6888a0148e06fe8de74811af  # 单集URL下载
  python main.py 682c566cc7c5f17595635a2c --max-episodes 50                     # 限制下载数量
  python main.py 682c566cc7c5f17595635a2c -o /path/to/download                  # 指定下载目录
  python main.py 682c566cc7c5f17595635a2c --save-only                           # 仅保存JSON，不下载
  python main.py 682c566cc7c5f17595635a2c --save-only --with-subtitles          # 保存JSON，下载字幕，不下载音频
  python main.py --from-json data/682c566cc7c5f17595635a2c.json                 # 从JSON文件下载
""")

    parser.add_argument('input', nargs='?', help='播客PID、单集EID或URL（播客的唯一标识符或网址）')
    parser.add_argument('--login', action='store_true', help='使用 refresh_token 和 device_id 登录')
    parser.add_argument('--refresh-token', help='直接提供 refresh_token 进行认证（需配合 --device-id）')
    parser.add_argument('--device-id', help='与 refresh_token 绑定的 device_id（x-jike-device-id）')
    parser.add_argument('--max-episodes', type=int, help='最大下载单集数量')
    parser.add_argument('--from-json', help='从指定JSON文件下载')
    parser.add_argument('--save-only', action='store_true', help='仅保存JSON数据，不下载文件')
    parser.add_argument('--with-subtitles', action='store_true', help='同时也下载字幕文件（如果有）')
    parser.add_argument('--info', action='store_true', help='显示详细信息（播客、主播或单集），不下载')
    parser.add_argument('--no-metadata', action='store_true', help='不保存元数据文件（JSON/MD）')
    parser.add_argument('--output', '-o', help='指定下载目录 (默认: download)')

    return parser


def interactive_mode():
    """交互式模式"""
    try:
        print("🎧 小宇宙播客下载器 - 交互式模式")
        print("=" * 50)

        # 创建认证实例
        auth = XiaoyuzhouAuth()

        # 优先尝试加载已保存的认证信息
        print("🔍 检查已保存的认证信息...")
        if auth.load_credentials():
            print("✅ 找到已保存的认证信息")

            # 验证认证信息是否有效
            print("🔐 验证认证信息有效性...")
            if auth.ensure_valid_token():
                print("✅ 认证信息有效，可以直接使用")
            else:
                print("⚠️ 认证信息已失效，需要重新登录")
                if not auth.interactive_login():
                    print("❌ 登录失败，无法继续")
                    return False
        else:
            print("❌ 未找到已保存的认证信息，需要先登录")
            if not auth.interactive_login():
                print("❌ 登录失败，无法继续")
                return False

        print("\n📋 请提供要下载的播客信息:")

        # 获取播客ID或URL
        while True:
            user_input = input("请输入播客ID、单集URL或播客URL: ").strip()
            if not user_input:
                print("❌ 输入不能为空")
                continue

            # 检测输入类型
            input_type, extracted_id = detect_input_type(user_input)
            if input_type == "unknown":
                print("❌ 无法识别的ID或URL格式")
                print("💡 支持的格式:")
                print("   - 播客ID: 6603ea352d9eae5d0a5f9151")
                print("   - 播客URL: https://www.xiaoyuzhoufm.com/podcast/6603ea352d9eae5d0a5f9151")
                print("   - 单集URL: https://www.xiaoyuzhoufm.com/episode/6888a0148e06fe8de74811af")
                continue

            if not is_valid_podcast_id(extracted_id):
                print("❌ ID格式不正确")
                continue

            break

        print(f"✅ 识别到{input_type}: {extracted_id}")

        # 获取下载选项
        print("\n🔧 下载选项:")
        print("   1. 开始下载")
        print("   2. 仅保存JSON")
        print("   3. 查看详细信息")
        
        choice = input("\n请选择操作 (默认 1): ").strip()
        
        save_only = False
        if choice == "2":
            save_only = True
        elif choice == "3":
            downloader = XiaoyuzhouDownloader(auth=auth)
            return downloader.display_info(input_type, extracted_id)

        # 询问是否下载字幕
        with_subtitles = False
        sub_input = input("是否下载字幕 (y/N): ").strip().lower()
        if sub_input == 'y':
            with_subtitles = True
            print("📝 将下载字幕文件")

        # 如果是单集，跳过其他选项
        if input_type == "episode":
            if save_only:
                print(f"\n🚀 开始保存单集数据...")
            else:
                print("📻 检测到单集URL，将直接下载该单集")
                print(f"\n🚀 开始下载单集...")

            try:
                downloader = XiaoyuzhouDownloader(auth=auth)
                if not downloader:
                    print("❌ 创建下载器失败")
                    return False

                result = downloader.download_single_episode(extracted_id, save_only=save_only, with_subtitles=with_subtitles)

                if result and result.get('success'):
                    print("\n🎉 操作完成!")
                    # print(json.dumps(result, ensure_ascii=False, indent=2))
                    return True
                else:
                    print("❌ 操作失败")
                    return False

            except Exception as e:
                print(f"❌ 操作过程中发生错误: {e}")
                return False

        # 最大集数限制
        max_episodes = None
        max_input = input("最大下载集数 (回车跳过): ").strip()
        if max_input:
            try:
                max_episodes = int(max_input)
                print(f"📊 将限制下载 {max_episodes} 集")
            except ValueError:
                print("⚠️ 集数格式不正确，将下载所有集数")

        # 下载目录设置
        download_dir = None
        dir_input = input(f"下载目录 (默认 {config.download_dir}): ").strip()
        if dir_input:
            download_dir = dir_input
            print(f"📁 将下载到: {download_dir}")
        
        # 元数据保存设置
        save_metadata = True
        meta_input = input("是否保存元数据 JSON/MD (Y/n): ").strip().lower()
        if meta_input == 'n':
            save_metadata = False
            print("🚫 将不保存元数据文件")

        # 开始下载
        print(f"\n🚀 开始{'保存数据' if save_only else '下载'}...")

        try:
            # 如果指定了下载目录，设置到配置中
            if download_dir:
                config.set_download_dir(download_dir)

            downloader = XiaoyuzhouDownloader(auth=auth, save_metadata=save_metadata)
            if not downloader:
                print("❌ 创建下载器失败")
                return False

            if save_only:
                result = downloader.save_only(extracted_id, max_episodes, with_subtitles=with_subtitles)
            else:
                result = downloader.download(extracted_id, max_episodes, with_subtitles=with_subtitles)

            if result:
                print("\n🎉 操作完成!")
                # print(json.dumps(result, ensure_ascii=False, indent=2))
                return True
            else:
                print("❌ 操作失败")
                return False

        except Exception as e:
            print(f"❌ 操作过程中发生错误: {e}")
            return False

    except KeyboardInterrupt:
        print("\n⚠️ 交互式模式被用户中断")
        return False


def handle_login(refresh_token: str = None, device_id: str = None) -> bool:
    """处理登录流程"""
    try:
        auth = XiaoyuzhouAuth()

        if refresh_token and device_id:
            print("🔑 正在使用提供的 refresh_token 和 device_id 登录...")
            result = auth.login_with_refresh_token(refresh_token, device_id)
            if result["success"]:
                print("✅ 登录成功！")
                auth.save_credentials()
                return True
            else:
                print(f"❌ 登录失败: {result.get('error', '未知错误')}")
                return False
        elif refresh_token:
            print("❌ 使用 --refresh-token 时必须同时提供 --device-id")
            print("💡 示例: python main.py --refresh-token <token> --device-id <device_id>")
            return False

        if auth.interactive_login():
            print("🎉 登录成功！现在可以使用其他功能了")
            return True
        else:
            print("❌ 登录失败")
            return False
    except Exception as e:
        print(f"❌ 登录过程中发生错误: {e}")
        return False


def handle_download(args) -> bool:
    """处理下载流程"""
    try:
        # 如果指定了下载目录，设置到配置中
        if args.output:
            config.set_download_dir(args.output)
            print(f"📁 下载目录设置为: {args.output}", file=sys.stderr)

        # 创建认证实例
        auth = XiaoyuzhouAuth()

        # 创建下载器实例
        downloader = XiaoyuzhouDownloader(auth=auth, save_metadata=not args.no_metadata)

        if not downloader:
            print("❌ 创建下载器失败，请检查认证状态")
            return False

        # 根据参数执行不同的操作
        if args.from_json:
            # 从JSON文件下载
            print(f"🚀 从JSON文件下载: {args.from_json}", file=sys.stderr)
            result = downloader.download_from_json(args.from_json, with_subtitles=args.with_subtitles)
        else:
            # 检测输入类型并提取ID
            input_type, extracted_id = detect_input_type(args.input)
            if input_type == "unknown":
                print("❌ 无法识别的ID或URL格式")
                print("💡 支持的格式:")
                print("   - 播客ID: 6603ea352d9eae5d0a5f9151")
                print("   - 播客URL: https://www.xiaoyuzhoufm.com/podcast/6603ea352d9eae5d0a5f9151")
                print("   - 单集URL: https://www.xiaoyuzhoufm.com/episode/6888a0148e06fe8de74811af")
                return False

            if not is_valid_podcast_id(extracted_id):
                print("❌ ID格式不正确")
                return False

            print(f"✅ 识别到{input_type}: {extracted_id}", file=sys.stderr)

            # 如果只是查看信息
            if args.info:
                return downloader.display_info(input_type, extracted_id)

            # 如果是单集，使用单集下载方法
            if input_type == "episode":
                print(f"🚀 开始下载单集: {extracted_id}", file=sys.stderr)
                # 单集下载支持 --save-only 和 --with-subtitles
                result = downloader.download_single_episode(extracted_id, save_only=args.save_only, with_subtitles=args.with_subtitles)
            elif args.save_only:
                # 仅保存JSON
                print(f"🚀 仅保存JSON数据: {extracted_id}", file=sys.stderr)
                if args.max_episodes:
                    print(f"📊 限制数量: {args.max_episodes} 个单集", file=sys.stderr)
                result = downloader.save_only(extracted_id, args.max_episodes, with_subtitles=args.with_subtitles)
            else:
                # 正常下载播客
                print(f"🚀 开始下载播客: {extracted_id}", file=sys.stderr)
                if args.max_episodes:
                    print(f"📊 限制数量: {args.max_episodes} 个单集", file=sys.stderr)

                result = downloader.download(extracted_id, args.max_episodes, with_subtitles=args.with_subtitles)

        # 输出结果
        if result:
            return True
        else:
            print("❌ 操作失败")
            return False

    except Exception as e:
        print(f"❌ 操作失败: {e}", file=sys.stderr)
        return False


def main():
    """主函数"""
    parser = create_parser()
    args = parser.parse_args()

    # 显示欢迎信息
    print("🎧 小宇宙播客下载器", file=sys.stderr)
    print("📁 配置目录:", Path.cwd().absolute(), file=sys.stderr)
    print("", file=sys.stderr)

    # 处理登录请求
    if args.login or args.refresh_token:
        success = handle_login(args.refresh_token)
        sys.exit(0 if success else 1)

    # 如果没有提供任何参数，进入交互式模式
    if not args.input and not args.from_json:
        success = interactive_mode()
        sys.exit(0 if success else 1)

    # 检查必要参数
    if not args.from_json and not args.input:
        parser.error("必须提供播客PID/URL或使用--from-json指定JSON文件，或直接运行进入交互式模式")

    # 处理下载请求
    success = handle_download(args)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⚠️ 用户中断操作", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 程序异常退出: {e}", file=sys.stderr)
        sys.exit(1)
