#!/usr/bin/env python3
"""
Quick test agent — kirim data sample ke server pusat.
Jalankan SETELAH mendaftarkan server di dashboard dan mendapat token.

Usage:
  python3 test_agent.py --server http://localhost:8888 --token TOKEN_ANDA
  python3 test_agent.py --server http://localhost:8888 --token TOKEN --watch   # monitor live

Untuk menjalankan sebagai agent penuh (baca history lokal):
  python3 test_agent.py --server http://localhost:8888 --token TOKEN --live
"""

import sys
import time
import random
import socket
import subprocess
import os
import argparse
from datetime import datetime, timezone, timedelta

try:
    import requests
except ImportError:
    print("Install: pip3 install requests")
    sys.exit(1)


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def utc_ago(seconds):
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds)).isoformat()


SAMPLE_USERS = ["ubuntu", "deploy", "root", "admin", "developer", "jenkins"]
SAMPLE_IPS = ["192.168.1.10", "10.0.0.5", "172.16.0.20", "203.0.113.42"]
SAMPLE_TERMINALS = ["pts/0", "pts/1", "pts/2", "tty1"]
SAMPLE_DIRS = ["/home/ubuntu", "/var/www/html", "/opt/app", "/tmp", "/root"]

SAMPLE_COMMANDS = [
    # Low risk
    ("ls -la /var/www/html", 0, "low"),
    ("cat /etc/nginx/nginx.conf", 0, "low"),
    ("systemctl status nginx", 0, "low"),
    ("df -h", 0, "low"),
    ("free -m", 0, "low"),
    ("ps aux | grep python", 0, "low"),
    ("tail -f /var/log/nginx/access.log", 0, "low"),
    ("git status", 0, "low"),
    ("git log --oneline -10", 0, "low"),
    ("whoami", 0, "low"),
    ("uptime", 0, "low"),
    ("netstat -tlnp", 0, "low"),
    ("top -bn1 | head -20", 0, "low"),
    ("find /var/log -name '*.log' -mtime -1", 0, "low"),
    # Medium risk
    ("apt install -y python3-pip", 0, "medium"),
    ("pip install flask requests", 0, "medium"),
    ("chmod 755 /opt/app/deploy.sh", 0, "medium"),
    ("chown www-data:www-data /var/www/html", 0, "medium"),
    ("systemctl restart nginx", 0, "medium"),
    ("docker run -d -p 8080:80 nginx", 0, "medium"),
    ("crontab -e", 0, "medium"),
    ("wget https://example.com/script.sh", 0, "medium"),
    # High risk
    ("sudo rm -rf /tmp/old_backup", 0, "high"),
    ("chmod 777 /opt/uploads", 0, "high"),
    ("useradd -m newuser", 0, "high"),
    ("passwd ubuntu", 1, "high"),
    ("systemctl stop firewalld", 1, "high"),
    ("iptables -F", 0, "high"),
    ("docker rm -f $(docker ps -aq)", 0, "high"),
    # Critical
    ("rm -rf /var/log/*", 0, "critical"),
    ("dd if=/dev/zero of=/dev/sda bs=1M count=100", 1, "critical"),
]


def send_heartbeat(server_url: str, token: str) -> bool:
    try:
        resp = requests.post(
            f"{server_url}/api/agent/heartbeat",
            headers={"X-Agent-Token": token, "Content-Type": "application/json"},
            json={
                "hostname": socket.gethostname(),
                "ip_address": _get_local_ip(),
                "os_info": {"id": "ubuntu", "pretty_name": "Ubuntu 22.04 LTS", "kernel": "5.15.0"},
                "agent_version": "1.0.0-test",
                "timestamp": utc_now(),
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        print(f"  ✓ Heartbeat → server: {data.get('server_name', '?')}")
        return True
    except Exception as e:
        print(f"  ✗ Heartbeat failed: {e}")
        return False


def send_commands(server_url: str, token: str, commands: list) -> bool:
    try:
        resp = requests.post(
            f"{server_url}/api/agent/commands",
            headers={"X-Agent-Token": token, "Content-Type": "application/json"},
            json={"commands": commands},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        print(f"  ✓ Commands → ingested: {data.get('ingested', 0)}, alerts: {data.get('alerts_created', 0)}")
        return True
    except Exception as e:
        print(f"  ✗ Commands failed: {e}")
        return False


def send_sessions(server_url: str, token: str) -> bool:
    users_online = random.sample(SAMPLE_USERS[:4], k=random.randint(1, 3))
    active = []
    for u in users_online:
        active.append({
            "username": u,
            "remote_ip": random.choice(SAMPLE_IPS),
            "terminal": random.choice(SAMPLE_TERMINALS),
            "login_time": utc_ago(random.randint(60, 7200)),
            "idle_time": f"{random.randint(0, 30)}s",
            "current_process": random.choice(["bash", "vim /etc/nginx/nginx.conf", "python3 app.py", "top"]),
        })

    sessions = [{
        "username": u,
        "remote_ip": random.choice(SAMPLE_IPS),
        "terminal": random.choice(SAMPLE_TERMINALS),
        "login_time": utc_ago(random.randint(60, 86400)),
        "login_method": "ssh",
        "status": "active",
    } for u in users_online]

    try:
        resp = requests.post(
            f"{server_url}/api/agent/sessions",
            headers={"X-Agent-Token": token, "Content-Type": "application/json"},
            json={"sessions": sessions, "active_sessions": active},
            timeout=10,
        )
        resp.raise_for_status()
        print(f"  ✓ Sessions → active: {len(active)}")
        return True
    except Exception as e:
        print(f"  ✗ Sessions failed: {e}")
        return False


def read_local_history(max_lines: int = 50) -> list:
    """Baca bash history user saat ini untuk mode --live."""
    history_file = os.path.expanduser("~/.bash_history")
    commands = []
    try:
        with open(history_file) as f:
            lines = f.readlines()
        for line in lines[-max_lines:]:
            line = line.strip()
            if line and not line.startswith("#"):
                commands.append({
                    "username": os.getenv("USER", "unknown"),
                    "command": line,
                    "timestamp": utc_now(),
                    "remote_ip": None,
                    "terminal": os.getenv("SSH_TTY", "pts/0"),
                    "working_dir": os.getcwd(),
                    "exit_code": None,
                })
    except Exception:
        pass
    return commands


def _get_local_ip() -> str:
    try:
        import socket as s
        sock = s.socket(s.AF_INET, s.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except Exception:
        return "127.0.0.1"


def make_random_command_batch(count: int = 5) -> list:
    batch = []
    user = random.choice(SAMPLE_USERS)
    remote_ip = random.choice(SAMPLE_IPS)
    terminal = random.choice(SAMPLE_TERMINALS)
    work_dir = random.choice(SAMPLE_DIRS)

    for _ in range(count):
        cmd_text, exit_code, _ = random.choice(SAMPLE_COMMANDS)
        batch.append({
            "username": user,
            "command": cmd_text,
            "exit_code": exit_code,
            "remote_ip": remote_ip,
            "terminal": terminal,
            "working_dir": work_dir,
            "timestamp": utc_now(),
        })
    return batch


def run_sample_mode(server_url: str, token: str):
    """Kirim 1 batch sample data dan keluar."""
    print(f"\n🚀 ServerAgent Test — mengirim sample data ke {server_url}\n")

    print("[1/3] Heartbeat...")
    if not send_heartbeat(server_url, token):
        print("\n❌ Tidak bisa terhubung. Periksa server URL dan token.")
        return

    print("[2/3] Sample commands (30 commands termasuk yang berisiko)...")
    all_cmds = []
    # Kirim semua sample commands
    for cmd_text, exit_code, _ in SAMPLE_COMMANDS:
        user = random.choice(SAMPLE_USERS)
        all_cmds.append({
            "username": user,
            "command": cmd_text,
            "exit_code": exit_code,
            "remote_ip": random.choice(SAMPLE_IPS),
            "terminal": random.choice(SAMPLE_TERMINALS),
            "working_dir": random.choice(SAMPLE_DIRS),
            "timestamp": utc_ago(random.randint(0, 3600)),
        })
    send_commands(server_url, token, all_cmds)

    print("[3/3] Active sessions...")
    send_sessions(server_url, token)

    print("\n✅ Selesai! Buka dashboard dan refresh.")
    print(f"   Dashboard: http://localhost:8880")
    print(f"   API docs:  http://localhost:8888/api/docs\n")


def run_watch_mode(server_url: str, token: str, interval: int = 10):
    """Kirim data secara berkala untuk simulasi real-time."""
    print(f"\n👀 Watch mode — mengirim data setiap {interval} detik. Ctrl+C untuk stop.\n")
    hb_counter = 0
    try:
        while True:
            hb_counter += 1
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Cycle #{hb_counter}")

            if hb_counter % 3 == 1:
                send_heartbeat(server_url, token)

            batch = make_random_command_batch(count=random.randint(2, 6))
            send_commands(server_url, token, batch)

            if hb_counter % 2 == 0:
                send_sessions(server_url, token)

            print(f"  Menunggu {interval}s...\n")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n\nStopped.")


def run_live_mode(server_url: str, token: str, interval: int = 15):
    """Baca history bash lokal dan kirim ke server (seperti agent sungguhan)."""
    print(f"\n🔴 Live mode — membaca history bash lokal setiap {interval}s. Ctrl+C untuk stop.\n")
    last_pos = 0
    history_file = os.path.expanduser("~/.bash_history")

    try:
        with open(history_file) as f:
            content = f.readlines()
        last_pos = len(content)
        print(f"  History file: {history_file} ({last_pos} baris sudah ada, menunggu yang baru...)")
    except Exception as e:
        print(f"  Tidak bisa baca history: {e}")

    send_heartbeat(server_url, token)

    try:
        while True:
            time.sleep(interval)
            send_heartbeat(server_url, token)

            try:
                with open(history_file) as f:
                    lines = f.readlines()
                new_lines = lines[last_pos:]
                last_pos = len(lines)

                if new_lines:
                    cmds = []
                    for line in new_lines:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            cmds.append({
                                "username": os.getenv("USER", "unknown"),
                                "command": line,
                                "exit_code": None,
                                "remote_ip": None,
                                "terminal": os.getenv("SSH_TTY", "pts/0"),
                                "working_dir": os.getcwd(),
                                "timestamp": utc_now(),
                            })
                    if cmds:
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] {len(cmds)} command baru dari history lokal")
                        send_commands(server_url, token, cmds)

            except Exception as e:
                print(f"  Error baca history: {e}")

            send_sessions(server_url, token)
    except KeyboardInterrupt:
        print("\n\nStopped.")


def main():
    parser = argparse.ArgumentParser(description="ServerAgent Test Script")
    parser.add_argument("--server", default="http://localhost:8888", help="URL server pusat")
    parser.add_argument("--token", required=True, help="Agent token dari dashboard")
    parser.add_argument("--watch", action="store_true", help="Kirim data random secara berkala")
    parser.add_argument("--live", action="store_true", help="Monitor bash history lokal")
    parser.add_argument("--interval", type=int, default=10, help="Interval detik untuk watch/live mode")
    args = parser.parse_args()

    if args.live:
        run_live_mode(args.server, args.token, args.interval)
    elif args.watch:
        run_watch_mode(args.server, args.token, args.interval)
    else:
        run_sample_mode(args.server, args.token)


if __name__ == "__main__":
    main()
