# -*- coding: utf-8 -*-
"""FlyLink launcher for Chinese Windows users — no Node.js required."""
import os
import sys
import time
import socket
import subprocess
import webbrowser
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
RUNTIME_PY = ROOT / "runtime" / "python" / "python.exe"
RUNTIME_MG = ROOT / "runtime" / "python" / "flylink_manage.py"
VENV_PY = BACKEND / ".venv" / "Scripts" / "python.exe"
DIST_INDEX = ROOT / "frontend" / "dist" / "index.html"
LOG = ROOT / "FlyLink-start-log.txt"

# 默认保持路演可扫码访问：0.0.0.0。
# 如果只允许本机访问，可在启动前设置：
# FLYLINK_BIND_HOST=127.0.0.1
BIND_HOST = os.environ.get("FLYLINK_BIND_HOST", "0.0.0.0")

try:
    BIND_PORT = int(os.environ.get("FLYLINK_BIND_PORT", "8000"))
except ValueError:
    BIND_PORT = 8000

URL = f"http://127.0.0.1:{BIND_PORT}/"
API = f"http://127.0.0.1:{BIND_PORT}/api/common/stats/"


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def msgbox(text: str, title: str = "FlyLink 飞链") -> None:
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, text, title, 0x40)
    except Exception:
        print(text)
        input("按回车键退出...")


def port_in_use(port: int = 8000) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def http_ok(url: str, timeout: float = 1.5) -> bool:
    try:
        import urllib.request
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return 200 <= r.status < 500
    except Exception:
        return False

def get_lan_ip():
    """Try to find a LAN IP for roadshow QR-code access."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            if ip and not ip.startswith("127."):
                return ip
    except Exception:
        pass

    try:
        ip = socket.gethostbyname(socket.gethostname())
        if ip and not ip.startswith("127."):
            return ip
    except Exception:
        pass

    return ""


def get_lan_url():
    if BIND_HOST not in ("0.0.0.0", "::"):
        return ""
    ip = get_lan_ip()
    if not ip:
        return ""
    return f"http://{ip}:{BIND_PORT}/"


def unblock_tree(path: Path) -> None:
    """Remove Windows mark-of-the-web so downloaded zip files can run."""
    for p in path.rglob("*"):
        if p.is_file():
            zone = Path(str(p) + ":Zone.Identifier")
            try:
                if zone.exists():
                    zone.unlink()
            except Exception:
                pass
    # Also try PowerShell Unblock-File
    try:
        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"Get-ChildItem -LiteralPath '{path}' -Recurse -File | Unblock-File -ErrorAction SilentlyContinue",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except Exception:
        pass


def pick_python():
    if RUNTIME_PY.exists() and RUNTIME_MG.exists():
        return "runtime", RUNTIME_PY, [str(RUNTIME_MG)]
    if VENV_PY.exists():
        return "venv", VENV_PY, [str(BACKEND / "manage.py")]
    # system python
    return "system", Path("python"), [str(BACKEND / "manage.py")]


def ensure_venv_if_needed(mode: str):
    if mode != "system":
        return pick_python()
    if VENV_PY.exists():
        return "venv", VENV_PY, [str(BACKEND / "manage.py")]
    log("Creating venv and installing dependencies (first run)...")
    subprocess.check_call(["python", "-m", "venv", str(BACKEND / ".venv")])
    pip = BACKEND / ".venv" / "Scripts" / "pip.exe"
    subprocess.check_call([str(pip), "install", "-r", str(BACKEND / "requirements.txt")])
    return "venv", VENV_PY, [str(BACKEND / "manage.py")]


def run_manage(py: Path, args_prefix: list, manage_args: list) -> None:
    env = os.environ.copy()
    env["FLYLINK_BACKEND"] = str(BACKEND)
    env["PYTHONUTF8"] = "1"
    cmd = [str(py)] + args_prefix + manage_args
    log("RUN: " + " ".join(cmd))
    subprocess.check_call(cmd, cwd=str(BACKEND), env=env)


def start_server(py: Path, args_prefix: list) -> subprocess.Popen:
    env = os.environ.copy()
    env["FLYLINK_BACKEND"] = str(BACKEND)
    env["PYTHONUTF8"] = "1"
    cmd = [str(py)] + args_prefix + ["runserver", f"{BIND_HOST}:{BIND_PORT}", "--noreload"]
    log("START SERVER: " + " ".join(cmd))
    # Detached-ish minimized console on Windows
    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_CONSOLE  # type: ignore
    return subprocess.Popen(
        cmd,
        cwd=str(BACKEND),
        env=env,
        creationflags=creationflags,
    )


def wait_ready(seconds: int = 45) -> bool:
    log("Waiting for service...")
    for i in range(seconds):
        if http_ok(API) or http_ok(URL):
            log(f"Ready after {i + 1}s")
            return True
        time.sleep(1)
        if i % 5 == 4:
            log(f"... still waiting ({i + 1}s)")
    return False


def open_browser():
    log("Opening browser: " + URL)
    # Try several ways — common Chinese Windows browsers
    candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    for exe in candidates:
        if Path(exe).exists():
            try:
                subprocess.Popen([exe, URL])
                return
            except Exception:
                pass
    webbrowser.open(URL)


def main() -> int:
    if LOG.exists():
        try:
            LOG.unlink()
        except Exception:
            pass
    log(f"ROOT={ROOT}")
    log(f"BACKEND={BACKEND}")
    log(f"BIND={BIND_HOST}:{BIND_PORT}")
    log(f"LOCAL_URL={URL}")
    if get_lan_url():
        log(f"LAN_URL={get_lan_url()}")

    if not DIST_INDEX.exists():
        msgbox(
            "缺少前端文件 frontend\\dist\\index.html\n\n"
            "请确认：\n"
            "1. 已完整解压压缩包（不要直接在压缩包里双击）\n"
            "2. 解压后目录里能看到 Start.bat、backend、frontend、runtime"
        )
        return 1

    log("Unblocking downloaded files...")
    unblock_tree(ROOT)

    try:
        mode, py, prefix = pick_python()
        if mode == "system":
            # verify python exists
            try:
                subprocess.check_call(["python", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                msgbox(
                    "未找到内置 Python，也未安装本机 Python。\n\n"
                    "请重新下载完整绿色版（含 runtime 文件夹），\n"
                    "或安装 Python 3.10+ 并勾选 Add to PATH。\n"
                    "下载：https://www.python.org/downloads/"
                )
                return 1
            mode, py, prefix = ensure_venv_if_needed(mode)
        log(f"MODE={mode} PY={py}")

        # init db
        log("migrate / seed...")
        run_manage(py, prefix, ["migrate", "--run-syncdb"])
        try:
            run_manage(py, prefix, ["seed_demo"])
        except Exception as e:
            log(f"seed_demo warning: {e}")

        if port_in_use(BIND_PORT) and (http_ok(API) or http_ok(URL)):
            log("Already running")
            open_browser()
            msgbox(
                "FlyLink 已在运行，已为你打开网页。\n\n"
                f"地址：{URL}\n"
                "企业账号：enterprise1 / demo1234\n"
                "飞手账号：pilot1 / demo1234\n\n"
                "关闭请运行 Stop.bat"
            )
            return 0

        if port_in_use(BIND_PORT) and not http_ok(URL):
            log("Port 8000 occupied by other program")
            msgbox(
                "端口 8000 已被其他程序占用。\n"
                "请先关闭占用程序，或运行 Stop.bat 后再试。"
            )
            return 1

        proc = start_server(py, prefix)
        ok = wait_ready(50)
        if not ok:
            # show last lines of any crash
            try:
                out, err = proc.communicate(timeout=1)
            except Exception:
                pass
            msgbox(
                "服务启动超时，网页还不能打开。\n\n"
                "请把同目录下的 FlyLink-start-log.txt 发给对方排查。\n"
                "常见原因：解压不完整、杀毒拦截、端口被占用。"
            )
            return 1

        open_browser()
        lan_url = get_lan_url()
        lan_tip = f"\n\n路演扫码地址：\n{lan_url}" if lan_url else ""
        msgbox(
            "启动成功！浏览器应已打开。\n\n"
            f"若没有自动打开，请手动访问：\n{URL}"
            f"{lan_tip}\n\n"
            "企业：enterprise1 / demo1234\n"
            "飞手：pilot1 / demo1234\n\n"
            "用完请运行 Stop.bat 关闭"
        )
        return 0
    except Exception:
        err = traceback.format_exc()
        log(err)
        msgbox(
            "启动失败。\n\n"
            "请把 FlyLink-start-log.txt 发给提供方。\n\n"
            + err[-800:]
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
