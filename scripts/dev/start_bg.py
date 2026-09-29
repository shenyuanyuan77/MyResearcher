"""后台常驻启动器（测试/CI 用）：以 DETACHED_PROCESS 方式启动 MCP + 后端。

与 start_all.py 的区别：子进程完全脱离当前进程树（新进程组 + 分离控制台），
本脚本退出或被 kill 均不影响服务；也没有 SIGTERM 清理钩子。
停止请用：python scripts/dev/stop_bg.py（或 taskkill）。

用法：
  python scripts/dev/start_bg.py            # 启动 MCP + 后端
  python scripts/dev/start_bg.py --check    # 仅健康检查
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOG = ROOT / "logs"

# Windows：DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB
_WIN_FLAGS = 0x00000008 | 0x00000200 | 0x01000000


def _popen(cmd: list[str], log_name: str) -> subprocess.Popen:
    LOG.mkdir(exist_ok=True)
    logf = open(LOG / log_name, "a", encoding="utf-8")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    kwargs: dict = {"cwd": str(ROOT), "env": env, "stdout": logf, "stderr": subprocess.STDOUT}
    if os.name == "nt":
        kwargs["creationflags"] = _WIN_FLAGS
    else:
        kwargs["start_new_session"] = True
    return subprocess.Popen(cmd, **kwargs)


def _wait_http(url: str, timeout: float, expect_ready: bool = False) -> bool:
    import json
    import urllib.request

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as r:
                if not expect_ready:
                    return True
                d = json.loads(r.read().decode("utf-8", "ignore"))
                if d.get("runtime", {}).get("ready"):
                    return True
        except urllib.error.HTTPError as e:
            # streamable-http 端点对普通 GET 返回 406 —— 能应答即视为存活
            if not expect_ready and e.code in (400, 405, 406):
                return True
        except Exception:
            pass
        time.sleep(1.5)
    return False


def main() -> int:
    if "--check" in sys.argv:
        import urllib.request

        for url in ["http://127.0.0.1:7001/mcp", "http://127.0.0.1:8000/health"]:
            try:
                with urllib.request.urlopen(url, timeout=3) as r:
                    print(f"  {url} -> {r.status}")
            except Exception as e:
                print(f"  {url} -> DOWN ({e})")
        return 0

    print("[1/2] detached 启动学术 MCP (:7001)...")
    _popen([sys.executable, "-m", "mcp_server.server_main"], "mcp.log")
    if not _wait_http("http://127.0.0.1:7001/mcp", timeout=30):
        print("  [WARN] MCP 30s 未就绪，仍继续")
    print("[2/2] detached 启动后端 FastAPI (:8000)...")
    _popen([sys.executable, "-m", "api_view.web_main"], "backend.log")
    ok = _wait_http("http://127.0.0.1:8000/health", timeout=180, expect_ready=True)
    print("  [OK] 后端 Agent 就绪" if ok else "  [WARN] 后端未就绪（可能仍在加载）")
    print("启动完成（服务与本进程树已分离）。")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
