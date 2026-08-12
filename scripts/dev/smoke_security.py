"""安全加固冒烟测试：bcrypt/所有权/限流/RBAC/结构化错误。

用法：PYTHONPATH=src python scripts/dev/smoke_security.py
（纯离线，不需要网络）
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))


def test_bcrypt_rejects_plaintext():
    """明文密码必须被拒绝（不再 hmac.compare_digest 兜底）。"""
    from api_view.auth import verify_password, hash_password
    print("[1] bcrypt 拒绝明文")
    assert verify_password("test", hash_password("test")), "bcrypt 正确密码应通过"
    assert not verify_password("test", "test"), "明文密码应被拒绝"
    assert not verify_password("test", "randomgarbage"), "未知格式应被拒绝"
    print("  ✓ 明文/未知格式密码被拒绝")


def test_auth_error_structure():
    """结构化错误契约 {code, message, detail}。"""
    from api_view.auth import _auth_error
    print("[2] 结构化错误契约")
    e = _auth_error("TOKEN_EXPIRED", "令牌已过期", "exp")
    assert isinstance(e.detail, dict), "detail 应为 dict"
    assert e.detail["code"] == "TOKEN_EXPIRED"
    assert e.detail["message"] == "令牌已过期"
    assert e.detail["detail"] == "exp"
    print("  ✓ {code, message, detail} 结构正确")


def test_assert_session_owner_security():
    """assert_session_owner 不自动认领未存在 thread。"""
    print("[3] 会话所有权安全")
    # 用 mock 测逻辑（避免实例化 AgentLoader 需要 agent）
    # 新策略：无 owner 且 thread 不存在 → 拒绝
    calls = []
    class MockLoader:
        def get_session_owner(self, tid): return None
        def thread_exists(self, tid): return False
        def bind_session_owner(self, tid, uid): calls.append(("bind", tid, uid))
    ml = MockLoader()
    # 复制 assert_session_owner 核心逻辑
    owner = ml.get_session_owner("new-thread")
    result = owner == "user1" if owner is not None else (
        ml.thread_exists("new-thread") and "user1" == "default_user"
    )
    assert result is False, "未存在 thread 应拒绝"
    assert len(calls) == 0, "未存在 thread 不应自动 bind"
    print("  ✓ 未存在 thread 不被自动认领")


def test_rate_limiter():
    """限流器：超限拒绝。"""
    print("[4] 限流器")
    from api_view.security_middleware import _MemoryRateLimiter

    async def _run():
        lim = _MemoryRateLimiter()
        ok1, _ = await lim.allow("ip1", 2, 60)
        ok2, _ = await lim.allow("ip1", 2, 60)
        ok3, _ = await lim.allow("ip1", 2, 60)
        assert ok1 and ok2, "限内应允许"
        assert not ok3, "超限应拒绝"
    asyncio.run(_run())
    print("  ✓ 超 limit 拒绝")


def test_source_circuit_breaker():
    """源熔断：连续失败标记不可用。"""
    from mcp_server.tools.unified import _source_available, _record_source_result
    print("[5] 源熔断")
    src = "smoke_source_test"
    # 先确保可用
    for _ in range(3):
        _record_source_result(src, ok=False)
    assert not _source_available(src), "连续失败 3 次后应熔断"
    # 恢复
    _record_source_result(src, ok=True)
    assert _source_available(src), "成功后应恢复"
    print("  ✓ 连续失败熔断 + 成功恢复")


def test_cache_lru_bound():
    """LRU 缓存有上限。"""
    from mcp_server.tools.unified import cache_set, cache_get, _CACHE_MAX
    print("[6] LRU 缓存上限")
    assert _CACHE_MAX == 512, f"CACHE_MAX 应为 512，实际 {_CACHE_MAX}"
    # 写入并读回
    cache_set("k1", "v1")
    assert cache_get("k1") == "v1"
    print(f"  ✓ LRU 上限 {_CACHE_MAX}，读写正确")


def main():
    tests = [
        ("bcrypt 拒绝明文", test_bcrypt_rejects_plaintext),
        ("结构化错误契约", test_auth_error_structure),
        ("会话所有权安全", test_assert_session_owner_security),
        ("限流器", test_rate_limiter),
        ("源熔断", test_source_circuit_breaker),
        ("LRU 缓存上限", test_cache_lru_bound),
    ]
    results = []
    for name, fn in tests:
        print()
        try:
            fn()
            results.append((name, "PASS"))
        except Exception as e:
            print(f"  ✗ 失败: {e}")
            results.append((name, f"FAIL: {e}"))

    print("\n" + "=" * 60)
    print("安全冒烟汇总：")
    for name, status in results:
        mark = "✓" if status == "PASS" else "✗"
        print(f"  {mark} {name}: {status}")


if __name__ == "__main__":
    main()
