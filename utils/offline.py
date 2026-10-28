"""One switch for air-gapped runs.

L3MN05_OFFLINE=1 (or config `offline: true`) refuses outbound network calls.
Loopback and the configured local-model host stay open. Remote features should
check is_offline() and say they are disabled. The socket and subprocess hooks
are the backstop if a call site forgets.

This is an application switch, not a firewall. A machine with no public route
is the physical air gap. The switch is what stops this process from trying.
"""

import os
import socket
import subprocess

_TRUE = {"1", "true", "yes", "on"}

_ALWAYS_ALLOWED = {
    "localhost",
    "127.0.0.1",
    "::1",
    "0.0.0.0",
    "ollama",
    # Werkzeug discovers the local interface by connecting a UDP socket at
    # these fixed addresses. No payload is sent. Blocking them stops the
    # chat server from booting under the offline switch.
    "10.253.155.219",
    "fd31:f903:5ab5:1::1",
}

_NETWORK_BINARIES = {
    "curl",
    "wget",
    "ssh",
    "scp",
    "sftp",
    "nc",
    "ncat",
    "ping",
    "gh",
    "dig",
    "nslookup",
    "telnet",
}

_NETWORK_GIT = {"clone", "fetch", "pull", "push", "ls-remote"}

_installed = False
_orig_connect = None
_orig_connect_ex = None
_orig_getaddrinfo = None
_orig_create_connection = None
_orig_run = None
_orig_popen = None
_orig_check_call = None
_orig_check_output = None
_orig_call = None
_orig_send = None
_orig_sendto = None


class OfflineBlocked(RuntimeError):
    """Raised when offline mode refuses an outbound call."""


def offline_message(feature: str) -> str:
    return (
        f"Offline mode is on. {feature} is disabled. "
        "Only the local model is used."
    )


def offline_error(feature: str) -> str:
    """Same notice, prefixed so callers that treat ERROR as failure see it."""
    return "ERROR: " + offline_message(feature)


def is_offline(config=None) -> bool:
    """Env wins over the config file. Unset env falls through to `offline:`."""
    raw = os.getenv("L3MN05_OFFLINE")
    if raw is not None and raw.strip() != "":
        return raw.strip().lower() in _TRUE
    if config is None:
        from utils.config import load_config
        config = load_config()
    return bool(config.get("offline", False))


def _normalize_host(host) -> str:
    if host is None:
        return ""
    if isinstance(host, bytes):
        try:
            host = host.decode()
        except Exception:
            return ""
    text = str(host).strip().strip("[]").lower()
    if text.startswith("::ffff:"):
        text = text.split("::ffff:", 1)[1]
    return text


def _host_allowed(host) -> bool:
    text = _normalize_host(host)
    if not text:
        return True
    if text in _ALWAYS_ALLOWED:
        return True
    from utils.config import get_ollama_host
    configured = get_ollama_host()
    if configured and text == configured.lower():
        return True
    return False


def _address_host(address):
    if isinstance(address, tuple) and address:
        return address[0]
    if isinstance(address, str) and address.startswith("/"):
        return None  # AF_UNIX
    if isinstance(address, str):
        return address
    return None


def _check_host(host, purpose="connection"):
    if not is_offline():
        return
    if _host_allowed(host):
        return
    target = _normalize_host(host) or "remote host"
    raise OfflineBlocked(offline_message(f"Outbound {purpose} to {target}"))


def _guarded_connect(self, address):
    _check_host(_address_host(address), "connection")
    return _orig_connect(self, address)


def _guarded_connect_ex(self, address):
    _check_host(_address_host(address), "connection")
    return _orig_connect_ex(self, address)


def _guarded_getaddrinfo(host, port, *args, **kwargs):
    _check_host(host, "DNS lookup")
    return _orig_getaddrinfo(host, port, *args, **kwargs)


def _guarded_create_connection(address, *args, **kwargs):
    host = address[0] if isinstance(address, tuple) and address else address
    _check_host(host, "connection")
    return _orig_create_connection(address, *args, **kwargs)


def _guarded_send(self, data, *args, **kwargs):
    try:
        peer = self.getpeername()
    except OSError:
        peer = None
    if peer:
        _check_host(_address_host(peer), "send")
    return _orig_send(self, data, *args, **kwargs)


def _guarded_sendto(self, data, *args, **kwargs):
    address = None
    if args:
        if isinstance(args[0], tuple):
            address = args[0]
        elif len(args) > 1 and isinstance(args[-1], tuple):
            address = args[-1]
    flags_or_addr = kwargs.get("address")
    if isinstance(flags_or_addr, tuple):
        address = flags_or_addr
    if address is not None:
        _check_host(_address_host(address), "send")
    return _orig_sendto(self, data, *args, **kwargs)


def _git_positionals(argv):
    positionals = []
    skip_next = False
    for arg in argv:
        if skip_next:
            skip_next = False
            continue
        if arg in {"-C", "-c", "--git-dir", "--work-tree"}:
            skip_next = True
            continue
        if str(arg).startswith("-"):
            continue
        positionals.append(str(arg))
    return positionals


def blocked_command(cmd):
    """Return a short label if this argv must not run while offline, else None."""
    if isinstance(cmd, str):
        parts = cmd.split()
        if not parts:
            return None
        return blocked_command(parts)
    if not isinstance(cmd, (list, tuple)) or not cmd:
        return None
    exe = os.path.basename(str(cmd[0])).lower()
    if exe in _NETWORK_BINARIES:
        return exe
    if exe == "git":
        positionals = _git_positionals(list(cmd[1:]))
        if positionals and positionals[0] in _NETWORK_GIT:
            return f"git {positionals[0]}"
    return None


def _guard_argv(cmd):
    if not is_offline():
        return
    blocked = blocked_command(cmd)
    if blocked:
        raise OfflineBlocked(offline_message(f"Command '{blocked}'"))


def _guarded_run(cmd, *args, **kwargs):
    _guard_argv(cmd)
    return _orig_run(cmd, *args, **kwargs)


def _guarded_popen(cmd, *args, **kwargs):
    _guard_argv(cmd)
    return _orig_popen(cmd, *args, **kwargs)


def _guarded_call(cmd, *args, **kwargs):
    _guard_argv(cmd)
    return _orig_call(cmd, *args, **kwargs)


def _guarded_check_call(cmd, *args, **kwargs):
    _guard_argv(cmd)
    return _orig_check_call(cmd, *args, **kwargs)


def _guarded_check_output(cmd, *args, **kwargs):
    _guard_argv(cmd)
    return _orig_check_output(cmd, *args, **kwargs)


def install_network_guard():
    """Install process-wide hooks. Safe to call more than once.

    The hooks read is_offline() on every call, so tests can toggle the env var
    without reinstalling.
    """
    global _installed
    global _orig_connect, _orig_connect_ex, _orig_getaddrinfo, _orig_create_connection
    global _orig_run, _orig_popen, _orig_call, _orig_check_call, _orig_check_output
    global _orig_send, _orig_sendto
    if _installed:
        return

    _orig_connect = socket.socket.connect
    _orig_connect_ex = socket.socket.connect_ex
    _orig_getaddrinfo = socket.getaddrinfo
    _orig_create_connection = socket.create_connection
    _orig_send = socket.socket.send
    _orig_sendto = socket.socket.sendto
    socket.socket.connect = _guarded_connect
    socket.socket.connect_ex = _guarded_connect_ex
    socket.getaddrinfo = _guarded_getaddrinfo
    socket.create_connection = _guarded_create_connection
    socket.socket.send = _guarded_send
    socket.socket.sendto = _guarded_sendto

    _orig_run = subprocess.run
    _orig_popen = subprocess.Popen
    _orig_call = subprocess.call
    _orig_check_call = subprocess.check_call
    _orig_check_output = subprocess.check_output
    subprocess.run = _guarded_run
    subprocess.Popen = _guarded_popen
    subprocess.call = _guarded_call
    subprocess.check_call = _guarded_check_call
    subprocess.check_output = _guarded_check_output

    _installed = True


install_network_guard()
