"""Two-layer network isolation for A02 (mock/in-sample; no external calls).

Layer 1 (entry/transport guards): monkeypatched blocks on
socket.create_connection, socket.socket.connect, socket.getaddrinfo,
urllib.request.urlopen, httpx sync/async transports, and aiohttp. Every
blocked attempt raises NetworkBlockedError explicitly.

Layer 2 (OS sandbox): a probe executed under `unshare -r -n` (user-namespace
netns, no sudo) WITHOUT importing these Python patches. Isolation is proved
with (1) a parent-hosted listener as a positive control (reachable without
unshare), (2) a different /proc/self/ns/net inode under unshare, and (3)
the sandbox process failing to deliver TCP/UDP to that parent listener.
Arbitrary exceptions, TEST-NET connect timeouts, and UDP send-then-timeout
are not treated as deny evidence. A probe run without unshare is detected
as not isolated. Only this probe process is netns-isolated; the rest of
the suite is offline by construction, not by a process-tree unshare.

Missing logs/counters are never inferred as "zero external calls": the
runner requires one explicit record per expected attempt.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from contextlib import contextmanager, ExitStack
from unittest import mock

LABEL = "mock/in-sample"


class NetworkBlockedError(RuntimeError):
    """Explicit error raised by every blocked network entry."""


class OSProbeError(RuntimeError):
    """OS-layer probe unavailable or inconclusive (blocked, never skipped)."""


def _raise_blocked(entry: str):
    def _blocked(*args, **kwargs):
        raise NetworkBlockedError(
            f"offline-suite guard blocked network entry: {entry} ({LABEL})")
    return _blocked


async def _raise_blocked_async(entry: str, *args, **kwargs):
    raise NetworkBlockedError(
        f"offline-suite guard blocked network entry: {entry} ({LABEL})")


ENTRY_TARGETS = (
    "socket.create_connection",
    "socket.socket.connect",
    "socket.getaddrinfo",
    "urllib.request.urlopen",
    "httpx.HTTPTransport.handle_request",
    "httpx.AsyncHTTPTransport.handle_async_request",
    "aiohttp.ClientSession._request",
)

_ASYNC_ENTRIES = frozenset({
    "httpx.AsyncHTTPTransport.handle_async_request",
    "aiohttp.ClientSession._request",
})


def _patcher_for(entry: str):
    if entry in _ASYNC_ENTRIES:
        async def _impl(*args, **kwargs):
            raise NetworkBlockedError(
                f"offline-suite guard blocked network entry: {entry} ({LABEL})")
        return mock.patch(entry, new=_impl)
    return mock.patch(entry, new=_raise_blocked(entry))


@contextmanager
def network_guard(entries: tuple[str, ...] | None = None):
    """Activate guard patches for `entries` (default: all ENTRY_TARGETS)."""
    selected = tuple(entries) if entries is not None else ENTRY_TARGETS
    unknown = [e for e in selected if e not in ENTRY_TARGETS]
    if unknown:
        raise ValueError(f"unknown guard entries: {unknown}")
    with ExitStack() as stack:
        for entry in selected:
            stack.enter_context(_patcher_for(entry))
        yield selected


def verify_entries(entries: dict[str, object]) -> dict[str, dict]:
    """Run each entry callable; exactly NetworkBlockedError counts as
    blocked. A return value or any other outcome is NOT_BLOCKED, which is
    how the negative control detects a fake-success guard."""
    verdicts: dict[str, dict] = {}
    for name, attempt in entries.items():
        try:
            outcome = attempt()
        except NetworkBlockedError as exc:
            verdicts[name] = {"verdict": "blocked", "detail": str(exc)}
        except Exception as exc:  # noqa: BLE001 - any leak is evidence.
            verdicts[name] = {"verdict": "NOT_BLOCKED",
                              "detail": f"wrong outcome: {type(exc).__name__}: {exc}"}
        else:
            verdicts[name] = {"verdict": "NOT_BLOCKED",
                              "detail": f"returned success instead of blocking: {outcome!r}"}
    return verdicts


# ---------------------------------------------------------------------------
# Layer 2: OS-sandbox probe (stdlib only; never imports the Layer-1 patches).
# ---------------------------------------------------------------------------

OS_EXPECTED_ATTEMPTS = (
    "tcp_parent_listener",
    "udp_parent_listener",
    "ns_isolation",
    "inherited_sockets_closed",
    "grandchild_parent_listener",
)

OS_PROBE_SOURCE = r'''
import json
import os
import socket
import subprocess
import sys

evidence = {
    "role": os.environ.get("PROBE_ROLE", ""),
    "ns": None,
    "closed_inherited": [],
    "inherited_sockets": [],
    "attempts": {},
    "notes": "mock/in-sample isolation probe; parent-hosted listener; no external calls",
}

def record(name, **fields):
    evidence["attempts"][name] = fields

def scan_sockets():
    found = []
    try:
        fds = os.listdir("/proc/self/fd")
    except OSError as exc:
        return {"error": "cannot list fds: %s" % exc}
    for fd in fds:
        try:
            target = os.readlink(os.path.join("/proc/self/fd", fd))
        except OSError:
            continue
        if target.startswith("socket:"):
            found.append({"fd": int(fd), "target": target})
    return found

def close_inherited_sockets():
    closed = []
    remaining = []
    listing = scan_sockets()
    if isinstance(listing, dict) and "error" in listing:
        return listing, listing
    for item in listing:
        fd = item["fd"]
        if fd in (0, 1, 2):
            continue
        try:
            os.close(fd)
            closed.append(item["target"])
        except OSError:
            remaining.append(item)
    return closed, scan_sockets() if not (isinstance(listing, dict) and "error" in listing) else remaining

try:
    evidence["ns"] = os.readlink("/proc/self/ns/net")
except OSError as exc:
    evidence["ns"] = None
    evidence["ns_error"] = str(exc)

closed, remaining = close_inherited_sockets()
evidence["closed_inherited"] = closed if isinstance(closed, list) else []
evidence["inherited_sockets"] = remaining if isinstance(remaining, list) else remaining

host = os.environ["PARENT_PROBE_HOST"]
tcp_port = int(os.environ["PARENT_PROBE_TCP_PORT"])
udp_port = int(os.environ["PARENT_PROBE_UDP_PORT"])

# TCP: only a successful connect counts as reaching the parent. Timeouts
# and errno values are recorded; they are not auto-classified as blocked.
tcp_error = None
tcp_connected = False
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    sock.settimeout(2)
    sock.connect((host, tcp_port))
    tcp_connected = True
    try:
        sock.sendall(os.environ.get("PROBE_ROLE", "probe").encode())
    except Exception:
        pass
except Exception as exc:
    tcp_error = "%s: %s" % (type(exc).__name__, exc)
finally:
    sock.close()
record("tcp_parent_listener", connected=tcp_connected, error=tcp_error)

# UDP: send-then-timeout is NOT deny evidence. The parent receive counter
# is the isolation signal; this side only records send/recv outcomes.
udp_send_ok = False
udp_send_error = None
udp_recv_ok = False
udp_recv_error = None
usock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
try:
    usock.settimeout(1)
    usock.sendto(os.environ.get("PROBE_ROLE", "probe").encode(), (host, udp_port))
    udp_send_ok = True
    try:
        data, _addr = usock.recvfrom(512)
        udp_recv_ok = bool(data)
    except Exception as exc:
        udp_recv_error = "%s: %s" % (type(exc).__name__, exc)
except Exception as exc:
    udp_send_error = "%s: %s" % (type(exc).__name__, exc)
finally:
    usock.close()
record("udp_parent_listener", send_ok=udp_send_ok, send_error=udp_send_error,
       recv_ok=udp_recv_ok, recv_error=udp_recv_error)

# Grandchild (no Python patches) also targets the parent listener.
code = (
    "import socket, sys\n"
    "host, port, tag = sys.argv[1], int(sys.argv[2]), sys.argv[3]\n"
    "s = socket.socket(); s.settimeout(2)\n"
    "try:\n"
    "    s.connect((host, port)); s.sendall(tag.encode()); print('CONNECTED')\n"
    "except Exception as exc:\n"
    "    print('DENIED:%s:%s' % (type(exc).__name__, exc)); sys.exit(1)\n"
    "finally:\n"
    "    s.close()\n"
)
try:
    proc = subprocess.run(
        [sys.executable, "-c", code, host, str(tcp_port),
         os.environ.get("PROBE_ROLE", "probe")],
        timeout=10, capture_output=True, text=True)
    g_out = (proc.stdout or "").strip()
    g_err = (proc.stderr or "").strip()
    g_text = g_out or g_err
    record("grandchild_parent_listener",
           connected=proc.returncode == 0 and "CONNECTED" in g_out,
           launch_ok=True,
           output=g_out,
           error=None if proc.returncode == 0 else g_text[-300:])
except Exception as exc:
    record("grandchild_parent_listener", connected=False, launch_ok=False,
           output="", error="%s: %s" % (type(exc).__name__, exc))

print(json.dumps(evidence))
'''


def _read_ns() -> str | None:
    try:
        return os.readlink("/proc/self/ns/net")
    except OSError:
        return None


def _probe_bind_host() -> str:
    """Prefer a non-loopback IPv4. Fallback is 127.0.0.1 plus the ns check."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("192.0.2.1", 1))
        ip = sock.getsockname()[0]
    except OSError:
        ip = None
    finally:
        sock.close()
    if ip and not ip.startswith("127."):
        return ip
    return "127.0.0.1"


def _start_parent_listeners(host: str):
    tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    tcp.bind((host, 0))
    tcp.listen(8)
    tcp.settimeout(0.2)
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    udp.bind((host, 0))
    udp.settimeout(0.2)
    state = {"tcp_control": 0, "tcp_sandbox": 0, "tcp_untagged": 0,
             "udp_control": 0, "udp_sandbox": 0, "udp_untagged": 0,
             "stop": False}

    def _bucket(data):
        if data == b"control":
            return "control"
        if data == b"sandbox":
            return "sandbox"
        return "untagged"

    def tcp_loop():
        while not state["stop"]:
            try:
                conn, _addr = tcp.accept()
                try:
                    conn.settimeout(0.5)
                    tag = conn.recv(64)
                except OSError:
                    tag = b""
                finally:
                    conn.close()
                state["tcp_" + _bucket(tag)] += 1
            except socket.timeout:
                continue
            except OSError:
                break

    def udp_loop():
        while not state["stop"]:
            try:
                data, addr = udp.recvfrom(512)
                state["udp_" + _bucket(data)] += 1
                try:
                    udp.sendto(b"ack", addr)
                except OSError:
                    pass
            except socket.timeout:
                continue
            except OSError:
                break

    threads = [
        threading.Thread(target=tcp_loop, daemon=True),
        threading.Thread(target=udp_loop, daemon=True),
    ]
    for thread in threads:
        thread.start()
    return host, tcp, udp, state, threads


def _stop_listeners(tcp, udp, state, threads):
    state["stop"] = True
    for sock in (tcp, udp):
        try:
            sock.close()
        except OSError:
            pass
    for thread in threads:
        thread.join(timeout=2)


def _run_probe_process(*, role: str, host: str, tcp_port: int, udp_port: int,
                       python_exe: str, timeout: int, use_unshare: bool,
                       inherit_socket=None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PARENT_PROBE_HOST"] = host
    env["PARENT_PROBE_TCP_PORT"] = str(tcp_port)
    env["PARENT_PROBE_UDP_PORT"] = str(udp_port)
    env["PROBE_ROLE"] = role
    cmd = [python_exe, "-c", OS_PROBE_SOURCE]
    if use_unshare:
        cmd = ["unshare", "-r", "-n", *cmd]
    kwargs = dict(capture_output=True, text=True, timeout=timeout, env=env)
    if inherit_socket is not None:
        kwargs["pass_fds"] = (inherit_socket.fileno(),)
        kwargs["close_fds"] = True
    return subprocess.run(cmd, **kwargs)


def _parse_probe_stdout(proc: subprocess.CompletedProcess, role: str) -> dict:
    if proc.returncode not in (0, 1):
        # The probe script itself should exit 0 after printing JSON even
        # when connections fail. A crash is inconclusive, not a deny.
        raise OSProbeError(
            f"BLOCKED_ISOLATION: {role} probe process failed "
            f"rc={proc.returncode}: {(proc.stderr or '')[-1000:]}")
    lines = [line for line in (proc.stdout or "").splitlines() if line.strip()]
    try:
        evidence = json.loads(lines[-1]) if lines else None
    except ValueError:
        evidence = None
    if not isinstance(evidence, dict) or "attempts" not in evidence:
        raise OSProbeError(
            f"BLOCKED_ISOLATION: {role} probe produced no parseable evidence; "
            f"missing logs are not zero-traffic proof")
    return evidence


def finalize_os_evidence(evidence: dict) -> dict:
    """Classify control vs sandbox. Raises if evidence is incomplete.

    UDP send-then-timeout is not a deny. Isolation requires a different
    netns inode and no parent-listener delivery from the sandbox.
    """
    required = ("control", "sandbox", "parent_ns", "bind_host")
    missing_top = [k for k in required if k not in evidence]
    if missing_top:
        raise OSProbeError(
            f"BLOCKED_ISOLATION: OS probe incomplete, missing {missing_top}; "
            f"not counted as coverage")
    sandbox = evidence["sandbox"]
    control = evidence["control"]
    attempts = sandbox.get("attempts") or {}
    missing = [n for n in OS_EXPECTED_ATTEMPTS if n not in attempts]
    # ns_isolation and inherited_sockets_closed are synthesized below if
    # the raw fields exist; only the listener/grandchild keys must be raw.
    raw_required = ("tcp_parent_listener", "udp_parent_listener",
                    "grandchild_parent_listener")
    missing_raw = [n for n in raw_required if n not in attempts]
    if missing_raw:
        raise OSProbeError(
            f"BLOCKED_ISOLATION: OS probe incomplete, missing attempts "
            f"{missing_raw}; not counted as coverage")
    control_attempts = control.get("attempts") or {}
    if "tcp_parent_listener" not in control_attempts or "udp_parent_listener" not in control_attempts:
        raise OSProbeError(
            "BLOCKED_ISOLATION: OS probe incomplete, missing control attempts; "
            "not counted as coverage")

    def _required_count(key: str) -> int:
        if key not in evidence:
            raise OSProbeError(
                f"BLOCKED_ISOLATION: OS probe incomplete, missing {key}; "
                f"missing counters are not zero-traffic proof")
        val = evidence[key]
        if type(val) is not int or val < 0:
            raise OSProbeError(
                f"BLOCKED_ISOLATION: OS probe incomplete, {key}={val!r} "
                f"is not a recorded count")
        return val

    parent_ns = evidence["parent_ns"]
    sandbox_ns = sandbox.get("ns")
    ns_isolated = bool(parent_ns and sandbox_ns and sandbox_ns != parent_ns)
    attempts["ns_isolation"] = {
        "blocked": ns_isolated,
        "parent_ns": parent_ns,
        "sandbox_ns": sandbox_ns,
        "error": None if ns_isolated else "sandbox netns matches parent; not isolated",
    }
    if "inherited_sockets" not in sandbox or not isinstance(
            sandbox["inherited_sockets"], list):
        raise OSProbeError(
            "BLOCKED_ISOLATION: OS probe incomplete, "
            "sandbox inherited_sockets is not an explicit list; "
            "missing/null/non-list remaining-socket observations are "
            "inconclusive, not zero-remaining proof")
    inherited = sandbox["inherited_sockets"]
    closed = sandbox.get("closed_inherited") or []
    inherited_clean = inherited == []
    attempts["inherited_sockets_closed"] = {
        "blocked": inherited_clean and len(closed) >= 1,
        "inherited_sockets": inherited,
        "closed_inherited": closed,
        "error": None if inherited_clean and len(closed) >= 1 else (
            "inherited sockets not closed or none were presented to close"),
    }

    control_tcp_count = _required_count("control_tcp_accepts")
    control_udp_count = _required_count("control_udp_datagrams")
    sandbox_tcp_count = _required_count("sandbox_tcp_accepts")
    sandbox_udp_count = _required_count("sandbox_udp_datagrams")
    untagged_tcp_count = _required_count("untagged_tcp_accepts")
    untagged_udp_count = _required_count("untagged_udp_datagrams")
    if untagged_tcp_count > 0 or untagged_udp_count > 0:
        raise OSProbeError(
            "BLOCKED_ISOLATION: parent listener received untagged deliveries "
            f"(tcp={untagged_tcp_count}, udp={untagged_udp_count}); "
            "untagged traffic is inconclusive, neither sandbox evidence "
            "nor a pass")

    # Parent-counter evidence is authoritative for TCP/UDP isolation.
    tcp = attempts["tcp_parent_listener"]
    udp = attempts["udp_parent_listener"]
    sandbox_tcp_reached = bool(tcp.get("connected")) or sandbox_tcp_count > 0
    sandbox_udp_reached = sandbox_udp_count > 0 or bool(udp.get("recv_ok"))
    tcp["blocked"] = (not sandbox_tcp_reached) and ns_isolated
    tcp["parent_received"] = sandbox_tcp_count > 0
    udp["blocked"] = (not sandbox_udp_reached) and ns_isolated
    udp["parent_received"] = sandbox_udp_count > 0
    # Explicitly: send-then-timeout is not sufficient deny evidence.
    udp["send_then_timeout_is_not_deny"] = True

    grandchild = attempts["grandchild_parent_listener"]
    g_text = str(grandchild.get("output") or grandchild.get("error") or "")
    denied = g_text.startswith("DENIED:")
    network_denied = denied and any(
        token in g_text for token in (
            "ENETUNREACH", "ECONNREFUSED", "EHOSTUNREACH", "ENETDOWN", "EPERM",
            "Network is unreachable", "Connection refused", "No route to host",
            "Network is down", "Permission denied", "timed out", "TimeoutError",
            "ETIMEDOUT",
        )
    )
    if grandchild.get("launch_ok") is False:
        raise OSProbeError(
            "BLOCKED_ISOLATION: grandchild probe failed to launch; "
            "a launch failure is inconclusive, not deny evidence")
    # Only a network deny (errno/message token) counts. Any other output,
    # including a non-network DENIED: prefix (ValueError, IndexError,
    # crash), is inconclusive, not a block.
    if (not grandchild.get("connected")) and not network_denied:
        raise OSProbeError(
            "BLOCKED_ISOLATION: grandchild probe inconclusive "
            f"({g_text or 'no DENIED output'}); arbitrary exceptions are "
            "not deny evidence, not counted as isolation")
    grandchild["blocked"] = (
        (not bool(grandchild.get("connected"))) and ns_isolated
        and network_denied and sandbox_tcp_count == 0
    )
    grandchild["denied"] = denied
    grandchild["network_denied"] = network_denied
    grandchild["parent_received"] = sandbox_tcp_count > 0

    control_tcp = bool(control_attempts["tcp_parent_listener"].get("connected")) and control_tcp_count > 0
    control_udp = control_udp_count > 0 or bool(
        control_attempts["udp_parent_listener"].get("recv_ok"))
    control_grandchild = bool(
        control_attempts.get("grandchild_parent_listener", {}).get("connected"))
    control_same_ns = control.get("ns") == parent_ns
    evidence["control_reaches_parent"] = control_tcp and control_udp and control_grandchild
    evidence["control_same_ns_as_parent"] = control_same_ns
    evidence["ns_isolated"] = ns_isolated
    evidence["attempts"] = attempts
    if not (control_tcp and control_udp and control_grandchild and control_same_ns):
        raise OSProbeError(
            "BLOCKED_ISOLATION: parent listener positive control failed "
            "(without unshare the probe must reach the parent on TCP, UDP, "
            "and the grandchild path); not counted as isolation evidence")
    if not ns_isolated:
        raise OSProbeError(
            "BLOCKED_ISOLATION: sandbox netns equals parent; without-unshare "
            "path is detected as not isolated")
    if sandbox_tcp_reached or sandbox_udp_reached:
        raise OSProbeError(
            "BLOCKED_ISOLATION: sandbox reached the parent listener; "
            "isolation did not hold")
    return evidence


def run_os_sandbox_probe(python_exe: str | None = None,
                         timeout: int = 120) -> dict:
    """Execute the Layer-2 probe under `unshare -r -n` (no sudo).

    Raises OSProbeError when the mechanism is unavailable or the evidence
    is incomplete; callers must treat that as blocked, never as skip,
    coverage, or pass.
    """
    exe = python_exe or sys.executable
    if shutil.which("unshare") is None:
        raise OSProbeError("BLOCKED_ISOLATION: 'unshare' not found on PATH; "
                           "OS-layer netns probe unavailable")
    parent_ns = _read_ns()
    host = _probe_bind_host()
    tcp = udp = state = threads = dummy = None
    try:
        host, tcp, udp, state, threads = _start_parent_listeners(host)
        tcp_port = tcp.getsockname()[1]
        udp_port = udp.getsockname()[1]
        try:
            control_proc = _run_probe_process(
                role="control", host=host, tcp_port=tcp_port, udp_port=udp_port,
                python_exe=exe, timeout=timeout, use_unshare=False)
        except subprocess.TimeoutExpired as exc:
            raise OSProbeError(f"BLOCKED_ISOLATION: OS control probe timed out "
                               f"after {timeout}s: {exc}")
        control = _parse_probe_stdout(control_proc, "control")
        # Role-tagged payloads distinguish control from sandbox, so a late
        # control accept cannot be charged to the sandbox (and missing
        # counters stay missing rather than defaulting to zero).

        dummy = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sandbox_proc = _run_probe_process(
                role="sandbox", host=host, tcp_port=tcp_port, udp_port=udp_port,
                python_exe=exe, timeout=timeout, use_unshare=True,
                inherit_socket=dummy)
        except subprocess.TimeoutExpired as exc:
            raise OSProbeError(f"BLOCKED_ISOLATION: OS sandbox probe timed out "
                               f"after {timeout}s: {exc}")
        sandbox = _parse_probe_stdout(sandbox_proc, "sandbox")
        # Drain late deliveries before snapshotting counters: TCP accept
        # timeout is 0.2s and post-accept recv timeout is 0.5s, so wait at
        # least their sum to avoid missing a late sandbox accept.
        time.sleep(0.7)
        evidence = {
            "bind_host": host,
            "parent_ns": parent_ns,
            "control": control,
            "sandbox": sandbox,
            "control_tcp_accepts": state["tcp_control"],
            "control_udp_datagrams": state["udp_control"],
            "sandbox_tcp_accepts": state["tcp_sandbox"],
            "sandbox_udp_datagrams": state["udp_sandbox"],
            "untagged_tcp_accepts": state["tcp_untagged"],
            "untagged_udp_datagrams": state["udp_untagged"],
            "notes": "mock/in-sample; parent listener + netns inode; "
                     "suite itself is not process-tree unshared",
        }
        return finalize_os_evidence(evidence)
    finally:
        if dummy is not None:
            try:
                dummy.close()
            except OSError:
                pass
        if tcp is not None:
            _stop_listeners(tcp, udp, state, threads)
