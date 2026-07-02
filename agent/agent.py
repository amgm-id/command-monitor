#!/usr/bin/env python3
"""
ServerAgent Monitor - Linux Agent v1.1
Membaca command dari bash hook log, session dari wtmp/who,
lalu mengirim ke server pusat secara berkala.
"""

import os
import re
import sys
import json
import time
import socket
import logging
import subprocess
import signal
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

try:
    import yaml
    import requests
except ImportError:
    print("[ERROR] pip3 install pyyaml requests", file=sys.stderr)
    sys.exit(1)

# ── Konfigurasi ─────────────────────────────────────────────────────────────

DEFAULT_CONFIG = {
    "server_url": "https://your-central-server.com",
    "agent_token": "REPLACE_WITH_YOUR_TOKEN",
    "interval": 15,
    "command_log": "/var/log/serveragent/commands.log",
    "state_file": "/var/lib/serveragent/state.json",
    "auth_log_sources": ["/var/log/auth.log", "/var/log/secure"],
    "ssl_verify": True,
    "timeout": 10,
    "batch_size": 100,
    "debug": False,
}

CONFIG_PATHS = [
    "/etc/serveragent/config.yaml",
    "/opt/serveragent/config.yaml",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml"),
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("serveragent")

# ── Helpers ──────────────────────────────────────────────────────────────────

def load_config() -> Dict[str, Any]:
    cfg = DEFAULT_CONFIG.copy()
    for path in CONFIG_PATHS:
        if os.path.exists(path):
            try:
                with open(path) as f:
                    cfg.update(yaml.safe_load(f) or {})
                logger.info(f"Config: {path}")
            except Exception as e:
                logger.warning(f"Gagal baca config {path}: {e}")
            break
    return cfg


def utc_now() -> str:
    """Waktu sekarang (waktu lokal server = WITA)."""
    return datetime.now().isoformat()


def run_cmd(cmd: str, timeout: int = 5) -> str:
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except Exception:
        return ""


def get_hostname() -> str:
    return socket.gethostname()


def get_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    finally:
        try: s.close()
        except: pass


def get_os_info() -> Dict:
    info = {}
    try:
        for line in Path("/etc/os-release").read_text().splitlines():
            if "=" in line:
                k, _, v = line.partition("=")
                info[k.lower()] = v.strip('"')
    except Exception:
        pass
    info["kernel"] = run_cmd("uname -r")
    return info


def load_state(path: str) -> Dict:
    try:
        return json.loads(Path(path).read_text())
    except Exception:
        return {}


def save_state(path: str, state: Dict):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        Path(path).write_text(json.dumps(state))
    except Exception as e:
        logger.warning(f"Gagal simpan state: {e}")

# ── Pengumpulan data ──────────────────────────────────────────────────────────

def collect_from_hook_log(state: Dict, log_file: str) -> List[Dict]:
    """
    Sumber utama: baca dari /var/log/serveragent/commands.log
    Format per baris: timestamp|username|remote_ip|terminal|working_dir|exit_code|command
    """
    if not os.path.exists(log_file):
        return []

    pos = state.get("hook_log_pos", 0)
    commands = []

    try:
        size = os.path.getsize(log_file)
        # Jika file di-rotate (size lebih kecil dari posisi terakhir), mulai dari awal
        if size < pos:
            logger.info("Log file di-rotate, reset posisi")
            pos = 0

        with open(log_file, "r", errors="replace") as f:
            f.seek(pos)
            for line in f:
                line = line.rstrip("\n")
                if not line:
                    continue
                parts = line.split("|", 6)
                if len(parts) < 7:
                    continue

                ts_str, username, remote_ip, terminal, working_dir, exit_code_str, command = parts

                # Validasi
                if not command.strip() or not username.strip():
                    continue

                try:
                    exit_code = int(exit_code_str)
                except ValueError:
                    exit_code = None

                commands.append({
                    "username": username.strip(),
                    "command": command.strip(),
                    "remote_ip": remote_ip.strip() or None,
                    "terminal": terminal.strip() or None,
                    "working_dir": working_dir.strip() or None,
                    "exit_code": exit_code,
                    "timestamp": ts_str.strip(),
                })
            state["hook_log_pos"] = f.tell()
    except (PermissionError, IOError) as e:
        logger.warning(f"Tidak bisa baca {log_file}: {e}")

    if commands:
        logger.info(f"Dari hook log: {len(commands)} command baru")
    return commands


def collect_from_sudo_log(state: Dict, sources: List[str]) -> List[Dict]:
    """Backup: tangkap perintah sudo dari auth.log."""
    commands = []
    positions = state.get("auth_log_pos", {})
    pattern = re.compile(
        r"(\w+\s+\d+\s+\d+:\d+:\d+).*?sudo\[.*?\]:\s+(\S+)\s+:.*?COMMAND=(.+)"
    )

    for log in sources:
        if not os.path.exists(log):
            continue
        pos = positions.get(log, 0)
        try:
            with open(log, "r", errors="replace") as f:
                f.seek(pos)
                for line in f:
                    m = pattern.search(line)
                    if m:
                        commands.append({
                            "username": m.group(2),
                            "command": f"sudo {m.group(3).strip()}",
                            "remote_ip": None,
                            "terminal": None,
                            "working_dir": None,
                            "exit_code": None,
                            "timestamp": utc_now(),
                        })
                positions[log] = f.tell()
        except (PermissionError, IOError):
            pass

    state["auth_log_pos"] = positions
    return commands


def collect_from_auditd(state: Dict) -> List[Dict]:
    """Backup: gunakan ausearch jika auditd tersedia."""
    if not os.path.exists("/sbin/ausearch") and not os.path.exists("/usr/sbin/ausearch"):
        return []

    since_ts = state.get("ausearch_since", "")
    since_arg = f"--start {since_ts}" if since_ts else "--start today"

    output = run_cmd(
        f"ausearch -k cmd_exec {since_arg} -i --format csv 2>/dev/null | tail -200",
        timeout=10,
    )
    if not output:
        return []

    commands = []
    now = utc_now()
    for line in output.splitlines():
        parts = line.split(",")
        if len(parts) < 6:
            continue
        try:
            cmd = parts[5].strip().strip('"')
            username = parts[3].strip().strip('"') if len(parts) > 3 else "unknown"
            if cmd and username and cmd != "exe":
                commands.append({
                    "username": username,
                    "command": cmd,
                    "timestamp": now,
                    "remote_ip": None, "terminal": None,
                    "working_dir": None, "exit_code": None,
                })
        except Exception:
            pass

    # Simpan timestamp untuk query berikutnya
    state["ausearch_since"] = datetime.now().strftime("%H:%M:%S")
    if commands:
        logger.info(f"Dari auditd: {len(commands)} command baru")
    return commands


def collect_active_sessions() -> List[Dict]:
    """Baca sesi aktif dari 'w -h -s', PID dari 'who -u'."""
    # 'who -u' kolom PID bisa di posisi berbeda tergantung format tanggal.
    # Strategi: cari integer murni terakhir sebelum komentar dalam tanda kurung.
    pid_map: Dict[str, int] = {}
    who_out = run_cmd("who -u 2>/dev/null")
    for line in who_out.splitlines():
        parts = line.split()
        if len(parts) < 5:
            continue
        tty = parts[1]
        # Cari field integer murni (bukan dalam kurung) — itu PID
        for p in reversed(parts[2:]):
            if p.startswith('('):
                continue
            if re.match(r'^\d+$', p):
                candidate = int(p)
                if 1 <= candidate <= 4194304:
                    pid_map[tty] = candidate
                    break

    sessions = []
    out = run_cmd("w -h -s 2>/dev/null")
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        username = parts[0]
        terminal = parts[1]
        from_addr = parts[2]

        remote_ip = from_addr if (from_addr and from_addr != "-"
                                  and not from_addr.startswith(":")) else None
        idle = parts[3] if len(parts) > 3 else None
        process = " ".join(parts[5:]) if len(parts) > 5 else None

        sessions.append({
            "username": username,
            "remote_ip": remote_ip,
            "terminal": terminal,
            "login_time": utc_now(),
            "idle_time": idle,
            "current_process": process,
            "pid": pid_map.get(terminal),
        })
    return sessions


def parse_last_time(parts: list, offset: int) -> str:
    """Parse timestamp dari output 'last -F': 'Mon Jun 30 10:00:00 2026'.
    Output 'last -F' menggunakan waktu lokal (WITA) — simpan langsung.
    """
    if len(parts) < offset + 5:
        return utc_now()
    try:
        ts_str = " ".join(parts[offset:offset + 5])  # "Mon Jun 30 10:00:00 2026"
        dt = datetime.strptime(ts_str, "%a %b %d %H:%M:%S %Y")
        return dt.isoformat()
    except (ValueError, IndexError):
        return utc_now()


def collect_session_logs() -> List[Dict]:
    """Baca login history dari 'last -F' dengan timestamp login asli."""
    sessions = []
    seen = set()
    # -F: full date, -w: no truncate username, -n 100: 100 entri terakhir
    out = run_cmd("last -F -w -n 100 2>/dev/null | grep -v '^$' | grep -v 'wtmp begins'")

    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 7:
            continue
        username = parts[0]
        if username in ("reboot", "shutdown", "runlevel", "LOGIN", ""):
            continue
        terminal = parts[1]
        from_addr = parts[2]
        remote_ip = (from_addr
                     if from_addr and from_addr != "-" and not from_addr.startswith(":")
                     else None)

        # Login time ada di parts[3..7]: "Mon Jun 30 10:00:00 2026"
        login_time = parse_last_time(parts, 3)

        if "still logged in" in line or "still running" in line:
            status = "active"
        elif "gone - no logout" in line:
            status = "timeout"
        else:
            status = "ended"

        # Dedup lokal sebelum kirim (hindari kirim entri sama dua kali)
        key = (username, terminal, login_time[:16])  # menit-level precision
        if key in seen:
            continue
        seen.add(key)

        sessions.append({
            "username": username,
            "remote_ip": remote_ip,
            "terminal": terminal,
            "login_time": login_time,
            "login_method": "ssh" if remote_ip else "console",
            "status": status,
        })
    return sessions[:50]

# ── Eksekusi Aksi ────────────────────────────────────────────────────────────

KILL_WRAPPER = "/usr/local/bin/sa-kill-session"


def execute_kill_session(payload: Dict) -> tuple:
    """
    Hentikan sesi SSH/terminal via wrapper root (sa-kill-session).
    Wrapper dijalankan via sudo tanpa TTY.
    Returns: (success: bool, message: str)
    """
    terminal = payload.get("terminal") or ""
    pid = payload.get("pid")
    username = payload.get("username") or ""

    def _run(cmd: str, timeout: int = 5) -> tuple:
        """Return (returncode, stdout, stderr)."""
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
            return r.returncode, r.stdout.strip(), r.stderr.strip()
        except Exception as e:
            return -1, "", str(e)

    logger.info(f"kill_session: terminal={terminal!r} pid={pid} username={username!r} wrapper_ok={os.path.isfile(KILL_WRAPPER)}")

    pid_arg = str(pid) if pid else ""

    # ── Via wrapper (root via sudo) ───────────────────────────────────────────
    if os.path.isfile(KILL_WRAPPER):
        rc, out, err = _run(f"sudo {KILL_WRAPPER} '{terminal}' '{pid_arg}'")
        logger.info(f"  wrapper rc={rc} out={out!r} err={err!r}")
        if rc == 0:
            msg = f"Sesi dihentikan (terminal={terminal}" + (f", PID={pid}" if pid else "") + ")"
            return True, msg
        # Lanjut ke fallback jika wrapper gagal

    # ── Fallback: coba langsung (jika agent dijalankan sebagai root) ──────────
    if terminal:
        # Kumpulkan semua PID di terminal lalu kill sekaligus
        ps_out, _, _ = _run(f"ps -t {terminal} -o pid= 2>/dev/null")
        pids = [p.strip() for p in ps_out.splitlines() if p.strip().isdigit()]
        if pids:
            rc, out, err = _run(f"kill -9 {' '.join(pids)}")
            logger.info(f"  kill pids={pids} rc={rc} err={err!r}")
            if rc == 0:
                return True, f"Sesi dihentikan (terminal {terminal})"

        rc, out, err = _run(f"pkill -KILL -t {terminal}")
        logger.info(f"  pkill -t {terminal!r} rc={rc} err={err!r}")
        if rc == 0:
            return True, f"Sesi dihentikan (terminal {terminal})"

    if pid:
        rc, out, err = _run(f"kill -9 {pid}")
        logger.info(f"  kill -9 {pid} rc={rc} err={err!r}")
        if rc == 0:
            return True, f"Sesi dihentikan (PID {pid})"

    logger.warning(f"Gagal menghentikan sesi: terminal={terminal!r} pid={pid}")
    return False, f"Gagal menghentikan sesi (terminal={terminal}, pid={pid})"


def process_actions(client) -> None:
    """Cek dan eksekusi aksi pending dari server pusat."""
    actions = client.get_pending_actions()
    if not actions:
        return

    for action in actions:
        action_id = action["id"]
        action_type = action["action_type"]
        payload = action.get("payload", {})

        logger.info(f"Aksi #{action_id}: {action_type} payload={payload}")

        if action_type == "kill_session":
            success, msg = execute_kill_session(payload)
            client.report_action_result(action_id, msg, success)
        else:
            client.report_action_result(action_id, f"Aksi tidak dikenal: {action_type}", False)


# ── API Client ────────────────────────────────────────────────────────────────

class AgentClient:
    def __init__(self, url: str, token: str, ssl_verify: bool = True, timeout: int = 10):
        self.url = url.rstrip("/")
        self.headers = {"X-Agent-Token": token, "Content-Type": "application/json"}
        self.ssl_verify = ssl_verify
        self.timeout = timeout

    def _post(self, path: str, data: dict) -> bool:
        try:
            r = requests.post(
                f"{self.url}/api{path}",
                json=data, headers=self.headers,
                verify=self.ssl_verify, timeout=self.timeout,
            )
            r.raise_for_status()
            return True
        except requests.exceptions.ConnectionError:
            logger.warning(f"Koneksi gagal ke {self.url}")
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP {e.response.status_code}: {e.response.text[:100]}")
        except requests.exceptions.Timeout:
            logger.warning("Request timeout")
        except Exception as e:
            logger.error(f"Error: {e}")
        return False

    def heartbeat(self) -> bool:
        uptime = None
        try:
            uptime = float(Path("/proc/uptime").read_text().split()[0])
        except Exception:
            pass
        return self._post("/agent/heartbeat", {
            "hostname": get_hostname(),
            "ip_address": get_ip(),
            "os_info": get_os_info(),
            "agent_version": "1.1.0",
            "uptime": uptime,
            "timestamp": utc_now(),
        })

    def send_commands(self, commands: List[Dict]) -> bool:
        if not commands:
            return True
        # Kirim dalam batch
        ok = self._post("/agent/commands", {"commands": commands})
        if ok:
            logger.info(f"✓ Terkirim {len(commands)} command")
        return ok

    def send_sessions(self, sessions: List[Dict], active: List[Dict]) -> bool:
        ok = self._post("/agent/sessions", {
            "sessions": sessions,
            "active_sessions": active,
        })
        if ok:
            logger.debug(f"✓ Sessions: {len(active)} aktif")
        return ok

    def get_pending_actions(self) -> List[Dict]:
        try:
            r = requests.get(
                f"{self.url}/api/agent/actions",
                headers=self.headers,
                verify=self.ssl_verify,
                timeout=self.timeout,
            )
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            logger.debug(f"Cek aksi gagal: {e}")
        return []

    def report_action_result(self, action_id: int, result: str, success: bool = True):
        try:
            requests.post(
                f"{self.url}/api/agent/actions/{action_id}/result",
                json={"result": result, "success": success},
                headers=self.headers,
                verify=self.ssl_verify,
                timeout=self.timeout,
            )
        except Exception as e:
            logger.debug(f"Lapor hasil aksi gagal: {e}")

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    cfg = load_config()

    if cfg["debug"]:
        logger.setLevel(logging.DEBUG)

    if cfg["agent_token"] == "REPLACE_WITH_YOUR_TOKEN":
        logger.error("Set agent_token di config.yaml terlebih dahulu!")
        sys.exit(1)

    client = AgentClient(
        cfg["server_url"],
        cfg["agent_token"],
        cfg.get("ssl_verify", True),
        cfg.get("timeout", 10),
    )

    state = load_state(cfg["state_file"])
    interval = cfg.get("interval", 15)
    batch_size = cfg.get("batch_size", 100)

    running = True
    def _stop(sig, frame):
        nonlocal running
        logger.info("Menghentikan agent...")
        running = False
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    logger.info(f"ServerAgent v1.1 — server: {cfg['server_url']} | interval: {interval}s")
    logger.info(f"Hostname: {get_hostname()} | IP: {get_ip()}")
    logger.info(f"Command log: {cfg['command_log']}")

    # Pastikan command log directory ada
    log_dir = os.path.dirname(cfg["command_log"])
    os.makedirs(log_dir, exist_ok=True)

    heartbeat_tick = 0
    session_tick = 0

    while running:
        try:
            heartbeat_tick += 1
            session_tick += 1

            # Heartbeat setiap ~2 menit (8 cycle × 15s)
            if heartbeat_tick >= 8:
                client.heartbeat()
                heartbeat_tick = 0

            # Kumpulkan command dari semua sumber
            commands = []
            commands += collect_from_hook_log(state, cfg["command_log"])
            commands += collect_from_sudo_log(state, cfg.get("auth_log_sources", []))
            commands += collect_from_auditd(state)

            # Deduplikasi berdasarkan hash
            seen = set()
            unique = []
            for c in commands:
                key = f"{c['username']}:{c['command']}:{c['timestamp']}"
                if key not in seen:
                    seen.add(key)
                    unique.append(c)

            # Kirim dalam batch
            for i in range(0, len(unique), batch_size):
                if not running:
                    break
                client.send_commands(unique[i:i + batch_size])

            # Cek aksi pending (kill session, dll) setiap cycle
            process_actions(client)

            # Session update setiap ~1 menit (4 cycle)
            if session_tick >= 4:
                active = collect_active_sessions()
                logs = collect_session_logs()
                client.send_sessions(logs, active)
                session_tick = 0

            save_state(cfg["state_file"], state)

        except Exception as e:
            logger.error(f"Error di loop utama: {e}", exc_info=cfg.get("debug"))

        for _ in range(interval):
            if not running:
                break
            time.sleep(1)

    logger.info("Agent berhenti.")


if __name__ == "__main__":
    main()
