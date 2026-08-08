"""一键关联启动：NapCat + YOUchat 串起来跑。

用法：
    python start.py               # 向导式一键启动
    python start.py --napcat D:/NapCat   # 指定 NapCat 目录

流程：
1. 检查 NapCat 目录 / 是否在跑 / 反向 WS 是否配好
2. 反向 WS 未配 → 打印 WebUI 配置引导，等 6700 就绪
3. NapCat 未跑 → 启动 launcher.bat
4. 读 settings 自动连 QQ 机器人（start_qq）
5. 启动 Web UI，自动开浏览器
"""
from __future__ import annotations

import argparse
import ctypes
import json
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

REPO = Path(__file__).resolve().parent
NAPCAT_DIR = REPO / "NapCat"
WEBUI_PORT = 6099      # NapCat 管理面板
REVERSE_WS_PORT = 6700  # 我们适配器监听的反向 WS（NapCat 连过来）
DEFAULT_WS_URL = f"ws://127.0.0.1:{REVERSE_WS_PORT}"


def is_admin() -> bool:
    """当前进程是否管理员权限。"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:  # noqa: BLE001
        return False


def port_open(port: int, host: str = "127.0.0.1", timeout: float = 0.5) -> bool:
    """检查端口是否监听。"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((host, port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def _qq_process_exists() -> bool:
    """检查 QQ.exe 进程是否在跑（判断 NapCat 是否真正登录）。"""
    try:
        out = subprocess.run(["tasklist"], capture_output=True, text=True, timeout=10).stdout
        return "QQ.exe" in out
    except (subprocess.SubprocessError, OSError):
        return False


def check_env(napcat_dir: Path):
    """检查环境，返回诊断信息 dict。"""
    onebot = list((napcat_dir / "config").glob("onebot11_*.json"))
    diag = {
        "napcat_dir_exists": napcat_dir.exists(),
        "napcat_running": port_open(WEBUI_PORT),
        "qq_running": _qq_process_exists(),
        "reverse_ws_ready": port_open(REVERSE_WS_PORT),
        "onebot11_exists": len(onebot) > 0,
    }
    return diag


def get_napcat_webui_url(napcat_dir: Path) -> str:
    """读取 NapCat webui.json 的 token，拼成带 token 的 WebUI 完整 URL。
    读不到返回不带 token 的基础 URL。
    """
    base = f"http://127.0.0.1:{WEBUI_PORT}/webui"
    cfg = napcat_dir / "config" / "webui.json"
    try:
        data = json.loads(cfg.read_text(encoding="utf-8"))
        token = data.get("token", "")
        if token:
            return f"{base}?token={token}"
    except (OSError, json.JSONDecodeError):
        pass
    return base


def ensure_reverse_ws(diag: dict, napcat_dir: Path) -> bool:
    """反向 WS 未配时引导用户在 WebUI 配，返回是否就绪。实时探测端口。"""
    if port_open(REVERSE_WS_PORT):
        print(f"  ✓ 反向 WebSocket 已就绪（端口 {REVERSE_WS_PORT}）")
        return True
    webui_url = get_napcat_webui_url(napcat_dir)
    print(f"""
  ⚠️ 检测到 NapCat 反向 WebSocket 未配置
     需要你手动配一次（之后每次启动都自动生效）：

     1. 浏览器打开（已自动带上 token，直接点开即可登录）：
        {webui_url}
        （如果打不开，token 在 NapCat 启动日志的『WebUi Token:』后面）
     2. 左侧「网络配置」→ 找到「Websocket 服务器」→ 新增
     3. Host 填：  127.0.0.1
     4. Port 填：  {REVERSE_WS_PORT}   ← 关键，NapCat 会监听这个端口
     5. 其他保持默认，保存

     配好后脚本会自动检测到端口 {REVERSE_WS_PORT} 就绪。""")
    # 轮询等 6700 端口就绪，最多 120s；用户回车可跳过
    print("     等待端口就绪（最多 2 分钟，配置好即自动继续；按回车跳过）...")
    wait_thread = threading.Thread(target=lambda: input(), daemon=True)
    wait_thread.start()
    deadline = time.time() + 120
    while time.time() < deadline:
        if port_open(REVERSE_WS_PORT):
            print("  ✓ 反向 WebSocket 已就绪")
            return True
        if not wait_thread.is_alive():  # 用户回车
            print("  已跳过，继续启动...")
            return False
        time.sleep(1)
    print("  等待超时，继续启动（机器人可能连不上，可稍后手动重试）...")
    return False


def ensure_napcat_running(diag: dict, napcat_dir: Path) -> bool:
    """NapCat 未跑时启动对应版本的启动脚本。"""
    if diag["napcat_running"] and diag["qq_running"]:
        print(f"  ✓ NapCat 已在运行（面板 {WEBUI_PORT}，QQ 已登录）")
        return True
    # 按版本选启动脚本：Framework 版用 napiLoader.bat，Shell 版用 launcher.bat
    candidates = []
    if (napcat_dir / "napimain.exe").exists():
        candidates = [napcat_dir / "napiLoader.bat", napcat_dir / "napiLoader-debug.bat"]
    if (napcat_dir / "NapCatWinBootMain.exe").exists():
        candidates += [napcat_dir / "launcher-win10.bat", napcat_dir / "launcher.bat"]
    launcher = next((p for p in candidates if p.exists()), None)
    if launcher is None:
        print(f"  ✗ 找不到 NapCat 启动脚本，请确认 NapCat 目录")
        return False
    print(f"  启动 NapCat（{launcher.name}，会弹出 QQ 登录窗口）...")
    try:
        subprocess.Popen(
            ["cmd", "/c", str(launcher)],
            cwd=str(napcat_dir),
            creationflags=subprocess.CREATE_NEW_CONSOLE,
        )
    except OSError as e:
        print(f"  ✗ 启动 NapCat 失败: {e}")
        return False
    # 等 WebUI 就绪且 QQ 进程在（确保真登录了）
    print("  等待 NapCat 就绪（会弹 QQ 登录窗口，请扫码登录）...")
    for _ in range(90):
        if port_open(WEBUI_PORT) and _qq_process_exists():
            print(f"  ✓ NapCat 已就绪（面板 {WEBUI_PORT}，QQ 已登录）")
            return True
        time.sleep(1)
    print("  ✗ NapCat 启动超时（可能弹了登录窗口等扫码，或权限不足）")
    print(f"    请以管理员身份运行本脚本，或手动双击 {launcher.name}")
    return False


def auto_connect_qq() -> bool:
    """读 settings 里存的 bot_qq/ws_url，自动启动 QQ 机器人。"""
    settings_path = REPO / "youchat" / "settings.json"
    if not settings_path.exists():
        print("  ✗ 未找到 settings.json（首次启动请在 Web UI 里填 bot_qq）")
        return False
    import json

    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    qq = settings.get("qq", {})
    bot_qq = str(qq.get("bot_qq", "") or "")
    ws_url = str(qq.get("ws_url", "") or DEFAULT_WS_URL)
    role = settings.get("default_role", "laomao")
    if not bot_qq:
        print("  ✗ settings 里没存 bot_qq（请先在 Web UI 的 QQ 接入里填一次）")
        return False
    print(f"  自动连接 QQ 机器人（角色 {role}，bot_qq={bot_qq}）...")
    try:
        sys.path.insert(0, str(REPO))
        from youchat.console.controller import AppController

        ctrl = AppController()  # 默认 resolve_project_root → youchat/ 包目录（config.yaml 所在）
        res = ctrl.start_qq(role, bot_qq, ws_url)
        if res.get("ok"):
            print(f"  ✓ QQ 机器人已启动（{ws_url}）")
            return True
        print(f"  ✗ 启动失败: {res.get('error')}")
    except Exception as e:  # noqa: BLE001
        print(f"  ✗ 自动连接失败: {e}")
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="一键启动 NapCat + YOUchat")
    parser.add_argument("--napcat", default=str(NAPCAT_DIR), help="NapCat 目录")
    parser.add_argument("--no-qq", action="store_true", help="不自动连 QQ 机器人")
    parser.add_argument("--no-admin-check", action="store_true", help="跳过管理员检查（测试用）")
    args = parser.parse_args()
    napcat_dir = Path(args.napcat)

    print("=" * 48)
    print("  YOUchat 一键启动")
    print("=" * 48)

    # 0. 管理员检查（NapCat 需要管理员权限）
    if not args.no_admin_check and not is_admin():
        print("""
  ⚠️ 需要管理员权限才能启动 NapCat

    请按以下步骤操作：
    1. 右键点击『开始』→『Windows PowerShell(管理员)』或『命令提示符(管理员)』
    2. 在弹出的窗口里输入：
         cd {repo}
         python start.py
    3. 重新运行本脚本

    如果 NapCat 已经在手动运行（launcher 窗口开着），可加 --no-admin-check 跳过检查。
""".format(repo=REPO))
        return 1

    # 1. 环境检查
    print("\n[1/4] 检查环境...")
    diag = check_env(napcat_dir)
    if not diag["napcat_dir_exists"]:
        print("  ⚠️ NapCat 未安装，尝试自动下载...")
        sys.path.insert(0, str(REPO))
        from install_napcat import main as install_main

        if install_main() != 0:
            print(f"  ✗ NapCat 安装失败，请手动安装到 {napcat_dir}")
            return 1
        diag = check_env(napcat_dir)
        print(f"  ✓ NapCat 已安装: {napcat_dir}")
    print(f"  ✓ NapCat 目录: {napcat_dir}")
    print(f"  ✓ QQ 进程: {'在运行' if diag['qq_running'] else '未运行'}")
    print(f"  ✓ 反向 WS: {'已就绪' if diag['reverse_ws_ready'] else '未就绪'}")

    # 2. NapCat 运行（先启动，再配/等反向 WS）
    print("\n[2/4] 检查 NapCat 运行状态...")
    ensure_napcat_running(diag, napcat_dir)

    # 3. 反向 WS（NapCat 起来后等 6700 就绪）
    print("\n[3/4] 检查反向 WebSocket...")
    if ensure_reverse_ws(diag, napcat_dir):
        diag["reverse_ws_ready"] = True

    # 4. 自动连 QQ + 启动 Web UI
    print("\n[4/4] 启动...")
    if not args.no_qq and diag["reverse_ws_ready"]:
        auto_connect_qq()
    elif args.no_qq:
        print("  已跳过自动连 QQ（--no-qq）")

    # 启动 Web UI
    print("\n启动 Web UI: http://127.0.0.1:5173")
    print("浏览器将自动打开；Ctrl+C 退出。\n")
    time.sleep(1)
    threading.Timer(2.0, lambda: webbrowser.open("http://127.0.0.1:5173")).start()
    sys.path.insert(0, str(REPO))
    from youchat import __main__ as m  # noqa: F401

    subprocess.call([sys.executable, "-m", "youchat", "--mode", "web"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
