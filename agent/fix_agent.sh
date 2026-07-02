#!/bin/bash
# ServerAgent Monitor - Script Perbaikan Cepat
# Jalankan di server yang sudah install agent:
#   sudo bash fix_agent.sh
#
# Jika agent belum terinstall, jalankan install.sh lebih dulu.

set -e

CMD_LOG_DIR="/var/log/serveragent"
CMD_LOG="$CMD_LOG_DIR/commands.log"
HOOK_FILE="/etc/profile.d/serveragent_hook.sh"
INSTALL_DIR="/opt/serveragent"
SERVICE="serveragent"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
log()  { echo -e "${GREEN}[✓]${NC} $*"; }
info() { echo -e "${CYAN}[→]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }

[[ $EUID -ne 0 ]] && { echo -e "${RED}[✗] Jalankan sebagai root: sudo bash fix_agent.sh${NC}"; exit 1; }

echo ""
echo -e "${CYAN}╔══════════════════════════════════════╗${NC}"
echo -e "${CYAN}║   ServerAgent - Fix Capture           ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════╝${NC}"
echo ""

# Step 1: Buat direktori log
info "Membuat direktori log..."
mkdir -p "$CMD_LOG_DIR"
touch "$CMD_LOG"
# Permission: semua user bisa tulis (-wx = 3, w=2), owner/group bisa baca
chmod 733 "$CMD_LOG_DIR"
chmod 622 "$CMD_LOG"
if id serveragent &>/dev/null; then
    chown serveragent:serveragent "$CMD_LOG" "$CMD_LOG_DIR" || true
fi
log "Log file: $CMD_LOG (permission: 622, dir: 733)"

# Step 2: Pasang bash hook
info "Memasang bash hook..."
cat > "$HOOK_FILE" <<'HOOK'
# ServerAgent Monitor - bash command capture hook
_SA_LOG="/var/log/serveragent/commands.log"

_sa_capture() {
    local _ec=$?
    local _cmd
    _cmd=$(HISTTIMEFORMAT='' history 1 2>/dev/null | sed 's/^[[:space:]]*[0-9][0-9]*[[:space:]]*//')
    [ -z "$_cmd" ] && return $_ec
    [ "$_cmd" = "$_SA_LAST_CMD" ] && return $_ec
    _SA_LAST_CMD="$_cmd"

    printf '%s|%s|%s|%s|%s|%s|%s\n' \
        "$(date '+%Y-%m-%dT%H:%M:%S')" \
        "$(id -un 2>/dev/null || echo unknown)" \
        "${SSH_CLIENT%% *}" \
        "$(tty 2>/dev/null | sed 's|^/dev/||')" \
        "$PWD" \
        "$_ec" \
        "$_cmd" >> "$_SA_LOG" 2>/dev/null
    return $_ec
}

shopt -s histappend 2>/dev/null
HISTCONTROL=ignoredups
HISTSIZE=50000

if [[ "$PROMPT_COMMAND" != *"_sa_capture"* ]]; then
    PROMPT_COMMAND="_sa_capture${PROMPT_COMMAND:+; $PROMPT_COMMAND}"
fi
HOOK

chmod 644 "$HOOK_FILE"
log "Hook: $HOOK_FILE"

# Tambahkan ke .bashrc root juga
if ! grep -q "_sa_capture" /root/.bashrc 2>/dev/null; then
    echo "" >> /root/.bashrc
    echo "[ -f $HOOK_FILE ] && source $HOOK_FILE" >> /root/.bashrc
    log ".bashrc root diupdate"
fi

# Step 3: Update agent.py
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "$SCRIPT_DIR/agent.py" && -d "$INSTALL_DIR" ]]; then
    info "Mengupdate agent.py..."
    cp "$SCRIPT_DIR/agent.py" "$INSTALL_DIR/agent.py"
    if id serveragent &>/dev/null; then
        chown serveragent:serveragent "$INSTALL_DIR/agent.py"
    fi
    log "agent.py diupdate"
fi

# Step 3b: Pastikan sudo terinstall
if ! command -v sudo &>/dev/null; then
    info "Menginstall sudo..."
    apt-get install -y sudo 2>/dev/null || yum install -y sudo 2>/dev/null || true
fi

# Buat wrapper kill session (dijalankan root via sudo)
info "Membuat wrapper sa-kill-session..."
KILL_WRAPPER="/usr/local/bin/sa-kill-session"
cat > "$KILL_WRAPPER" <<'KILLSCRIPT'
#!/bin/bash
# Wrapper kill session untuk ServerAgent
# Usage: sa-kill-session <terminal> [pid]
TERMINAL="$1"
PID="$2"

if [[ -n "$PID" ]] && [[ "$PID" =~ ^[0-9]+$ ]]; then
    if kill -9 "$PID" 2>/dev/null; then
        echo "killed pid=$PID"
        exit 0
    fi
fi

if [[ -n "$TERMINAL" ]]; then
    # Cari semua PID di terminal lalu kill
    PIDS=$(ps -t "$TERMINAL" -o pid= 2>/dev/null | tr '\n' ' ')
    if [[ -n "$PIDS" ]]; then
        kill -9 $PIDS 2>/dev/null
        echo "killed pids=$PIDS terminal=$TERMINAL"
        exit 0
    fi
    # Fallback pkill
    if pkill -KILL -t "$TERMINAL" 2>/dev/null; then
        echo "pkill ok terminal=$TERMINAL"
        exit 0
    fi
fi

echo "no process found terminal=$TERMINAL pid=$PID" >&2
exit 1
KILLSCRIPT
chmod 755 "$KILL_WRAPPER"
chown root:root "$KILL_WRAPPER"
log "Wrapper: $KILL_WRAPPER"

# Sudoers: wrapper + hapus file lama jika ada
SUDOERS_FILE="/etc/sudoers.d/serveragent-kill"
cat > "$SUDOERS_FILE" <<EOF
Defaults:serveragent !requiretty
serveragent ALL=(ALL) NOPASSWD: $KILL_WRAPPER
EOF
chmod 440 "$SUDOERS_FILE"
# Validasi sudoers
if visudo -c -f "$SUDOERS_FILE" &>/dev/null; then
    log "Sudoers kill OK: $SUDOERS_FILE"
else
    warn "Sudoers tidak valid — hapus untuk keamanan"
    rm -f "$SUDOERS_FILE"
fi

# Step 4: Reset state (agar agent baca dari awal)
STATE="/var/lib/serveragent/state.json"
if [[ -f "$STATE" ]]; then
    info "Reset posisi hook_log_pos di state file..."
    python3 -c "
import json, sys
try:
    s = json.loads(open('$STATE').read())
    s.pop('hook_log_pos', None)
    open('$STATE', 'w').write(json.dumps(s))
    print('State diupdate')
except Exception as e:
    print(f'Skip: {e}')
"
fi

# Step 5: Restart service
if systemctl is-enabled "$SERVICE" &>/dev/null 2>&1; then
    info "Merestart service $SERVICE..."
    systemctl restart "$SERVICE"
    sleep 2
    if systemctl is-active --quiet "$SERVICE"; then
        log "Service $SERVICE aktif"
    else
        warn "Service tidak aktif — cek: journalctl -u $SERVICE -n 20"
    fi
fi

# Step 6: Test hook langsung
info "Mengaktifkan hook di sesi saat ini..."
source "$HOOK_FILE"
log "Hook aktif di sesi ini"

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   Perbaikan selesai!                                      ║${NC}"
echo -e "${GREEN}╠══════════════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║${NC} 1. Coba jalankan perintah, lalu cek:"
echo -e "${GREEN}║${NC}    ${CYAN}tail -f $CMD_LOG${NC}"
echo -e "${GREEN}║${NC}"
echo -e "${GREEN}║${NC} 2. Cek log agent:"
echo -e "${GREEN}║${NC}    ${CYAN}journalctl -u $SERVICE -f${NC}"
echo -e "${GREEN}║${NC}"
echo -e "${GREEN}║${NC} 3. Untuk sesi SSH lain yang sudah terbuka:"
echo -e "${GREEN}║${NC}    ${CYAN}source $HOOK_FILE${NC}"
echo -e "${GREEN}║${NC}"
echo -e "${GREEN}║${NC} 4. Sesi baru akan aktif otomatis (hook di /etc/profile.d)"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
