"""A02: two-layer network isolation (mock/in-sample; no external calls).

Layer 1 blocks every transport/entry with an explicit error. Layer 2 is an
OS sandbox probe under `unshare -r -n` that never imports the Layer-1
patches. A parent-hosted listener plus netns inode (not TEST-NET
timeouts) prove isolation; a without-unshare run is detected. A fake-success
negative control must be detected. Unavailable probes block, never skip.
"""

from __future__ import annotations

import asyncio
import socket
import urllib.request
from unittest import mock

import pytest

from ._netguard import (
    ENTRY_TARGETS, OS_EXPECTED_ATTEMPTS, NetworkBlockedError, OSProbeError,
    network_guard, run_os_sandbox_probe, verify_entries,
)

REQUIRED_BRANCHES = [
    "transport_blocked",
    "os_sandbox_deny",
    "os_probe_fail_closed",
    "negative_control",
    "without_unshare_not_isolated",
]


def _attempt(entry: str):
    if entry == "socket.create_connection":
        return lambda: socket.create_connection(("192.0.2.1", 80), timeout=2)
    if entry == "socket.socket.connect":
        def connect():
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                sock.connect(("192.0.2.1", 9))
            finally:
                sock.close()
        return connect
    if entry == "socket.getaddrinfo":
        return lambda: socket.getaddrinfo("probe.invalid", 80)
    if entry == "urllib.request.urlopen":
        return lambda: urllib.request.urlopen("http://probe.invalid/", timeout=2)
    if entry == "httpx.HTTPTransport.handle_request":
        def sync_fetch():
            import httpx
            httpx.get("http://probe.invalid/", timeout=2)
        return sync_fetch
    if entry == "httpx.AsyncHTTPTransport.handle_async_request":
        async def async_fetch():
            import httpx
            async with httpx.AsyncClient() as client:
                await client.get("http://probe.invalid/", timeout=2)
        return lambda: asyncio.run(async_fetch())
    if entry == "aiohttp.ClientSession._request":
        async def aio_fetch():
            import aiohttp
            async with aiohttp.ClientSession() as session:
                await session.get("http://probe.invalid/", timeout=2)
        return lambda: asyncio.run(aio_fetch())
    raise AssertionError(f"unknown entry {entry}")


@pytest.mark.parametrize("entry", ENTRY_TARGETS,
                         ids=["transport_blocked_create_connection",
                              "transport_blocked_socket_connect",
                              "transport_blocked_getaddrinfo",
                              "transport_blocked_urlopen",
                              "transport_blocked_httpx_sync",
                              "transport_blocked_httpx_async",
                              "transport_blocked_aiohttp"])
def test_A02_network_guard_transport_blocked_per_entry(entry):
    """Each entry blocked in isolation with an explicit error (no network)."""
    with network_guard(entries=(entry,)):
        with pytest.raises(NetworkBlockedError, match="blocked network entry"):
            _attempt(entry)()


def test_A02_network_guard_transport_blocked_all_enabled():
    """All patches at once: every entry still raises the explicit error."""
    with network_guard():
        for entry in ENTRY_TARGETS:
            with pytest.raises(NetworkBlockedError):
                _attempt(entry)()


def test_A02_network_guard_os_sandbox_deny_no_bypass():
    """OS-layer probe (no Python patches): parent listener is reachable
    without unshare, sandbox netns differs, parent is not reached from
    the sandbox, inherited sockets are closed. UDP send-then-timeout is
    not treated as deny; parent receive counters are."""
    try:
        evidence = run_os_sandbox_probe()
    except OSProbeError as exc:
        pytest.fail(f"BLOCKED (not skip): {exc}")
    attempts = evidence["attempts"]
    assert set(OS_EXPECTED_ATTEMPTS) <= set(attempts), (
        f"incomplete OS evidence: {sorted(attempts)}")
    assert evidence["control_reaches_parent"] is True
    assert evidence["control_same_ns_as_parent"] is True
    assert evidence["ns_isolated"] is True
    for name in OS_EXPECTED_ATTEMPTS:
        record = attempts[name]
        assert record.get("blocked") is True, (
            f"OS sandbox permitted {name}: {record}")
    assert attempts["tcp_parent_listener"].get("connected") is False
    assert attempts["tcp_parent_listener"].get("parent_received") is False
    udp = attempts["udp_parent_listener"]
    assert udp.get("parent_received") is False
    assert udp.get("send_then_timeout_is_not_deny") is True
    assert attempts["grandchild_parent_listener"].get("connected") is False
    inherited = attempts["inherited_sockets_closed"]
    assert inherited.get("inherited_sockets") == []
    assert len(inherited.get("closed_inherited") or []) >= 1


def test_A02_network_guard_os_probe_fail_closed_not_skip_or_coverage():
    """Unavailable/incomplete OS probes block with a reason; they are never
    read as skip, coverage, or pass."""
    with mock.patch("shutil.which", return_value=None):
        with pytest.raises(OSProbeError, match="BLOCKED_ISOLATION"):
            run_os_sandbox_probe()
    incomplete = mock.Mock(returncode=0,
                           stdout='{"attempts": {"tcp_parent_listener": {"connected": false}}}',
                           stderr="")
    with mock.patch("subprocess.run", return_value=incomplete):
        with pytest.raises(OSProbeError, match="incomplete"):
            run_os_sandbox_probe()


def test_A02_network_guard_os_sandbox_without_unshare_not_isolated():
    """A probe that never entered a new netns is detected as not isolated
    (positive control reaches the parent, sandbox ns equals parent)."""
    from ._netguard import finalize_os_evidence
    parent_ns = "net:[111]"
    control_attempts = {
        "tcp_parent_listener": {"connected": True, "error": None},
        "udp_parent_listener": {"send_ok": True, "recv_ok": True},
        "grandchild_parent_listener": {"connected": True},
    }
    # Same payload reused as a fake "sandbox" that actually ran unsandboxed.
    with pytest.raises(OSProbeError, match="not isolated"):
        finalize_os_evidence({
            "bind_host": "127.0.0.1",
            "parent_ns": parent_ns,
            "control": {"ns": parent_ns, "attempts": control_attempts},
            "sandbox": {"ns": parent_ns, "attempts": dict(control_attempts),
                        "inherited_sockets": [], "closed_inherited": ["socket:[1]"]},
            "control_tcp_accepts": 1,
            "control_udp_datagrams": 1,
            "sandbox_tcp_accepts": 1,
            "sandbox_udp_datagrams": 1,
            "untagged_tcp_accepts": 0,
            "untagged_udp_datagrams": 0,
        })


def _passing_os_evidence():
    """Fresh valid finalize_os_evidence fixture: isolated sandbox, positive
    control reaches the parent, explicit inherited list, zero untagged."""
    parent_ns = "net:[111]"
    control_attempts = {
        "tcp_parent_listener": {"connected": True, "error": None},
        "udp_parent_listener": {"send_ok": True, "send_error": None,
                                "recv_ok": True, "recv_error": None},
        "grandchild_parent_listener": {"connected": True, "launch_ok": True,
                                       "output": "CONNECTED", "error": None},
    }
    sandbox_attempts = {
        "tcp_parent_listener": {"connected": False,
                                "error": "TimeoutError: timed out"},
        "udp_parent_listener": {"send_ok": True, "send_error": None,
                                "recv_ok": False,
                                "recv_error": "TimeoutError: timed out"},
        "grandchild_parent_listener": {
            "connected": False, "launch_ok": True, "output": "",
            "error": "DENIED:OSError:[Errno 101] Network is unreachable"},
    }
    return {
        "bind_host": "127.0.0.1",
        "parent_ns": parent_ns,
        "control": {"ns": parent_ns, "attempts": control_attempts},
        "sandbox": {"ns": "net:[222]", "attempts": sandbox_attempts,
                    "inherited_sockets": [],
                    "closed_inherited": ["socket:[5]"]},
        "control_tcp_accepts": 1,
        "control_udp_datagrams": 1,
        "sandbox_tcp_accepts": 0,
        "sandbox_udp_datagrams": 0,
        "untagged_tcp_accepts": 0,
        "untagged_udp_datagrams": 0,
    }


def test_A02_network_guard_finalize_accepts_valid_isolated_evidence():
    """Guard for the new required keys: fully observed isolated evidence
    (explicit inherited list, zero untagged) still finalizes blocked."""
    from ._netguard import finalize_os_evidence
    evidence = finalize_os_evidence(_passing_os_evidence())
    for name in OS_EXPECTED_ATTEMPTS:
        assert evidence["attempts"][name].get("blocked") is True, (
            f"valid isolated evidence not blocked for {name}")


def test_A02_network_guard_finalize_non_network_denied_is_inconclusive():
    """B-11: a grandchild DENIED: prefix without a network token
    (arbitrary exception) is inconclusive, never a block."""
    from ._netguard import finalize_os_evidence
    evidence = _passing_os_evidence()
    grandchild = evidence["sandbox"]["attempts"]["grandchild_parent_listener"]
    grandchild["output"] = "DENIED:ValueError:bad probe"
    grandchild["error"] = "DENIED:ValueError:bad probe"
    with pytest.raises(OSProbeError, match="inconclusive"):
        finalize_os_evidence(evidence)


@pytest.mark.parametrize("bad_value", ["__MISSING__", None,
                                       {"error": "cannot list fds: boom"}],
                         ids=["missing", "none", "error_dict"])
def test_A02_network_guard_finalize_inherited_sockets_must_be_explicit(
        bad_value):
    """B-18: missing/null/non-list inherited_sockets with a nonempty closed
    list must raise (must not coerce to [] and pass the close check)."""
    from ._netguard import finalize_os_evidence
    evidence = _passing_os_evidence()
    assert len(evidence["sandbox"]["closed_inherited"]) >= 1
    if bad_value == "__MISSING__":
        del evidence["sandbox"]["inherited_sockets"]
    else:
        evidence["sandbox"]["inherited_sockets"] = bad_value
    with pytest.raises(OSProbeError, match="inherited_sockets"):
        finalize_os_evidence(evidence)


@pytest.mark.parametrize("key", ["untagged_tcp_accepts",
                                 "untagged_udp_datagrams"])
def test_A02_network_guard_finalize_untagged_delivery_is_inconclusive(key):
    """B-18: any untagged parent-listener delivery is inconclusive, neither
    sandbox evidence nor a pass."""
    from ._netguard import finalize_os_evidence
    evidence = _passing_os_evidence()
    evidence[key] = 1
    with pytest.raises(OSProbeError, match="untagged"):
        finalize_os_evidence(evidence)


def test_A02_network_guard_negative_control_detects_fake_success():
    """A fake entry returning success instead of blocking must be detected
    by the harness, inside the isolation layer (no real network)."""
    def fake_broken_entry():
        return "success"  # Simulates a guard that silently lets traffic out.

    with network_guard(entries=("socket.getaddrinfo",)):
        verdicts = verify_entries({
            "socket.getaddrinfo": _attempt("socket.getaddrinfo"),
            "fake_broken_entry": fake_broken_entry,
        })
    assert verdicts["socket.getaddrinfo"]["verdict"] == "blocked"
    assert verdicts["fake_broken_entry"]["verdict"] == "NOT_BLOCKED"
    assert "success" in verdicts["fake_broken_entry"]["detail"]
    # Acceptance fails while ANY entry is NOT_BLOCKED.
    assert any(v["verdict"] != "blocked" for v in verdicts.values())
