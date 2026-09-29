"""停止 start_bg.py 启动的后台服务（MCP :7001 + 后端 :8000）。

按端口找 PID 并 taskkill，与启动方式无关（也能停 start_all.py 的残留进程）。
"""
from __future__ import annotations

import re
import subprocess
import sys


def _pids_on_port(port: int) -> list[str]:
    out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True).stdout
    pids = set()
    for line in out.splitlines():
        if f":{port}" in line and "LISTENING" in line:
            m = re.search(r"(\d+)\s*$", line.strip())
            if m:
                pids.add(m.group(1))
    return sorted(pids)


def main() -> int:
    any_killed = False
    for port in (7001, 8000):
        for pid in _pids_on_port(port):
            subprocess.run(["taskkill", "/PID", pid, "/F"], capture_output=True)
            print(f"  :{port} -> killed PID {pid}")
            any_killed = True
    if not any_killed:
        print("没有运行中的服务。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
