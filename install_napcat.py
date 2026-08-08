"""NapCat 首次自动拉取。

检测 NapCat/ 是否已安装（NapCatWinBootMain.exe 存在）；
未安装 → 从 GitHub Releases 下载 NapCat.Framework.zip 并解压到 NapCat/。

用法：python install_napcat.py
"""
from __future__ import annotations

import io
import json
import sys
import urllib.request
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent
# 打包后 __file__ 在 _internal；NapCat 应装到用户工作目录（exe 旁，可写持久）
if getattr(sys, "frozen", False):
    NAPCAT_DIR = Path.cwd() / "NapCat"
else:
    NAPCAT_DIR = REPO / "NapCat"
# 官方 Framework 版标记（napimain.exe）；Shell 版用 NapCatWinBootMain.exe
FRAMEWORK_MARKERS = ["napimain.exe", "NapCatWinBootMain.exe"]

RELEASES_API = "https://api.github.com/repos/NapNeko/NapCatQQ/releases/latest"
FRAMEWORK_ASSET = "NapCat.Framework.zip"


def napcat_installed() -> bool:
    return any((NAPCAT_DIR / m).exists() for m in FRAMEWORK_MARKERS)


def find_framework_url() -> str:
    """从 GitHub Releases 拿 NapCat.Framework.zip 下载地址。"""
    req = urllib.request.Request(RELEASES_API, headers={"User-Agent": "merak-bot"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    for asset in data.get("assets", []):
        if asset.get("name") == FRAMEWORK_ASSET:
            return asset["browser_download_url"]
    raise RuntimeError(f"未找到 {FRAMEWORK_ASSET}，请检查 NapCat Releases")


def download_and_extract(url: str) -> None:
    """下载并解压，带重试（GitHub 偶发断连）。"""
    print(f"下载 NapCat: {url}")
    max_retries = 3
    data = b""
    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "merak-bot"})
            with urllib.request.urlopen(req, timeout=180) as resp:
                chunks = []
                while True:
                    chunk = resp.read(64 * 1024)
                    if not chunk:
                        break
                    chunks.append(chunk)
                data = b"".join(chunks)
            break
        except Exception as e:  # noqa: BLE001
            print(f"  下载失败（第 {attempt} 次）: {e}")
            if attempt == max_retries:
                raise
            print("  重试中...")
    print(f"  下载完成（{len(data)/1024/1024:.1f} MB），解压中...")
    NAPCAT_DIR.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        zf.extractall(NAPCAT_DIR)
    print(f"  已解压到 {NAPCAT_DIR}")


def main() -> int:
    if napcat_installed():
        print(f"✓ NapCat 已安装（{NAPCAT_DIR / FRAMEWORK_MARKERS[0]}）")
        return 0
    print("⚠️ 未检测到 NapCat，开始自动下载...")
    try:
        url = find_framework_url()
        download_and_extract(url)
    except Exception as e:  # noqa: BLE001
        print(f"✗ 自动下载失败: {e}")
        print("  请手动下载 NapCat（https://github.com/NapNeko/NapCatQQ/releases）")
        print("  选择 NapCat.Framework.zip，解压到本目录的 NapCat/ 文件夹")
        return 1
    if napcat_installed():
        print("✓ NapCat 安装完成")
        print("  提示：首次启动 NapCat 会生成 WebUI 登录 token（在启动日志『WebUi Token:』后）")
        print("        运行 start.py 会自动读取并给出带 token 的链接")
        return 0
    print("✗ 解压后未找到启动文件（napimain.exe），请检查 NapCat 目录")
    return 1


if __name__ == "__main__":
    sys.exit(main())
