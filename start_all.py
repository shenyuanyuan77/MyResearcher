"""
研途智探AI · 一键启动器。

启动顺序：学术 MCP → 后端 FastAPI → 前端 Vite。
带健康轮询与优雅退出。

用法：
  python start_all.py            # 启动全部
  python start_all.py --check    # 仅健康检查
  python start_all.py --no-frontend  # 不起前端
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PYTHON = sys.executable
procs: list[subprocess.Popen] = []


def env_with_pythonpath() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    return env


def wait_http(url: str, timeout: float = 120.0, expect_json_ready: bool = False) -> bool:
    import urllib.request
    import json

    deadline = time.time() + timeout
    last = ""
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as r:
                body = r.read().decode("utf-8", "ignore")
                if expect_json_ready:
                    try:
                        d = json.loads(body)
                        if d.get("runtime", {}).get("ready") if "runtime" in d else d.get("agent_ready"):
                            return True
                        last = f"not ready yet: {d.get('status')}"
                    except Exception:
                        return True  # 非 JSON 但 200，视为存活
                else:
                    return True
        except Exception as e:
            last = str(e)
        time.sleep(1.5)
    print(f"[wait_http] 超时等待 {url}: {last}")
    return False


def start_mcp() -> subprocess.Popen:
    print("[1/3] 启动学术 MCP (:7001)...")
    log = open(ROOT / "logs" / "mcp.log", "a", encoding="utf-8")
    p = subprocess.Popen(
        [PYTHON, "-m", "mcp_server.server_main"],
        cwd=str(ROOT),
        env=env_with_pythonpath(),
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    procs.append(p)
    return p


def start_backend(port: int) -> subprocess.Popen:
    print("[2/3] 启动后端 FastAPI (:8000)...")
    env = env_with_pythonpath()
    env["BACKEND_PORT"] = str(port)
    log = open(ROOT / "logs" / "backend.log", "a", encoding="utf-8")
    p = subprocess.Popen(
        [PYTHON, "-m", "api_view.web_main"],
        cwd=str(ROOT),
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    procs.append(p)
    return p


def start_frontend(port: int) -> subprocess.Popen:
    print("[3/3] 启动前端 Vite (:3001)...")
    fe_dir = ROOT / "frontend"
    if not (fe_dir / "node_modules").exists():
        print("  node_modules 不存在，先 npm install...")
        subprocess.run("npm install", cwd=str(fe_dir), shell=True, check=False)
    log = open(ROOT / "logs" / "frontend.log", "a", encoding="utf-8")
    # Windows 上 npm 是 npm.cmd，需 shell=True 或用 npm.cmd；跨平台用 shell
    is_win = os.name == "nt"
    p = subprocess.Popen(
        "npm run dev" if is_win else ["npm", "run", "dev"],
        cwd=str(fe_dir),
        env={**os.environ, "VITE_PORT": str(port)},
        stdout=log,
        stderr=subprocess.STDOUT,
        shell=is_win,
    )
    procs.append(p)
    return p


def cleanup(*_):
    print("\n[退出] 正在停止全部服务...")
    for p in reversed(procs):
        try:
            p.terminate()
        except Exception:
            pass
    time.sleep(1)
    for p in procs:
        try:
            if p.poll() is None:
                p.kill()
        except Exception:
            pass
    sys.exit(0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="仅健康检查")
    ap.add_argument("--no-frontend", action="store_true")
    ap.add_argument("--backend-port", type=int, default=8000)
    ap.add_argument("--frontend-port", type=int, default=3001)
    args = ap.parse_args()

    (ROOT / "logs").mkdir(exist_ok=True)
    (ROOT / "data").mkdir(exist_ok=True)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    if args.check:
        import urllib.request

        for url in ["http://127.0.0.1:7001/mcp", "http://127.0.0.1:8000/health"]:
            try:
                with urllib.request.urlopen(url, timeout=3) as r:
                    print(f"  {url} -> {r.status}")
            except Exception as e:
                print(f"  {url} -> DOWN ({e})")
        return

    start_mcp()
    if not wait_http("http://127.0.0.1:7001/mcp", timeout=30):
        print("[WARN] MCP 健康检查未通过，仍继续（后端会降级）")

    start_backend(args.backend_port)
    print("  等待后端 Agent 就绪（最多 180s）...")
    if wait_http(f"http://127.0.0.1:{args.backend_port}/health", timeout=180, expect_json_ready=True):
        print("  ✅ 后端 Agent 就绪")
    else:
        print("  ⚠️ 后端未就绪（可能仍在加载或降级）")

    if not args.no_frontend:
        try:
            start_frontend(args.frontend_port)
            time.sleep(3)
        except Exception as e:
            print(f"[WARN] 前端启动失败：{e}（后端/MCP 仍在运行；可手动 cd frontend && npm run dev）")

    print("=" * 56)
    print("研途智探AI 已启动")
    print(f"  前端：     http://localhost:{args.frontend_port}")
    print(f"  后端 API： http://localhost:{args.backend_port}/docs")
    print(f"  健康：     http://localhost:{args.backend_port}/health")
    print("  默认账号： yanjiu / yanjiu123")
    print("  按 Ctrl+C 停止全部服务")
    print("=" * 56)

    try:
        for p in procs:
            p.wait()
    except KeyboardInterrupt:
        cleanup()


if __name__ == "__main__":
    main()
