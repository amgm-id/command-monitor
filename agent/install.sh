#!/bin/bash
# ServerAgent Monitor - Installer v1.1
# Usage: sudo bash install.sh --server https://SERVER_URL --token TOKEN
set -e

AGENT_USER="serveragent"
INSTALL_DIR="/opt/serveragent"
CONFIG_DIR="/etc/serveragent"
STATE_DIR="/var/lib/serveragent"
CMD_LOG_DIR="/var/log/serveragent"
CMD_LOG="$CMD_LOG_DIR/commands.log"
SERVICE_NAME="serveragent"
HOOK_FILE="/etc/profile.d/serveragent_hook.sh"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
log()  { echo -e "${GREEN}[✓]${NC} $*"; }
info() { echo -e "${CYAN}[→]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }
err()  { echo -e "${RED}[✗]${NC} $*"; exit 1; }

# Parse arguments
SERVER_URL=""; AGENT_TOKEN=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --server) SERVER_URL="$2"; shift 2 ;;
        --token)  AGENT_TOKEN="$2"; shift 2 ;;
        *) echo "Unknown: $1"; exit 1 ;;
    esac
done

[[ -z "$SERVER_URL" ]]  && err "Butuh --server https://..."
[[ -z "$AGENT_TOKEN" ]] && err "Butuh --token TOKEN"
[[ $EUID -ne 0 ]]       && err "Jalankan sebagai root: sudo bash install.sh ..."

echo ""
echo -e "${CYAN}╔══════════════════════════════════════╗${NC}"
echo -e "${CYAN}║   ServerAgent Monitor Installer v1.1  ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════╝${NC}"
echo ""
info "Server  : $SERVER_URL"
info "Hostname: $(hostname)"
echo ""

# Deteksi OS
if command -v apt-get &>/dev/null; then
    PKG_MGR="apt-get"; OS_TYPE="debian"
elif command -v dnf &>/dev/null; then
    PKG_MGR="dnf"; OS_TYPE="rhel"
elif command -v yum &>/dev/null; then
    PKG_MGR="yum"; OS_TYPE="rhel"
else
    err "Package manager tidak dikenali"
fi
log "OS terdeteksi: $OS_TYPE ($PKG_MGR)"

# Install dependensi
info "Menginstall dependensi..."
if [[ $OS_TYPE == "debian" ]]; then
    apt-get update -qq
    apt-get install -y -qq python3 python3-pip python3-venv curl auditd 2>/dev/null || true
else
    $PKG_MGR install -y python3 python3-pip curl audit 2>/dev/null || true
fi
log "Dependensi terinstall"

# Buat user
if ! id "$AGENT_USER" &>/dev/null; then
    useradd -r -s /sbin/nologin -d "$INSTALL_DIR" "$AGENT_USER"
    log "User '$AGENT_USER' dibuat"
fi

# Buat direktori
mkdir -p "$INSTALL_DIR" "$CONFIG_DIR" "$STATE_DIR" "$CMD_LOG_DIR"
log "Direktori dibuat"

# Copy agent
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp "$SCRIPT_DIR/agent.py" "$INSTALL_DIR/"
log "Agent di-copy ke $INSTALL_DIR"

# Python virtualenv
info "Membuat Python virtualenv..."
python3 -m venv "$INSTALL_DIR/venv"
"$INSTALL_DIR/venv/bin/pip" install -q --upgrade pip
"$INSTALL_DIR/venv/bin/pip" install -q pyyaml requests
log "Virtualenv siap"

# Tulis config
cat > "$CONFIG_DIR/config.yaml" <<CONF
server_url: "${SERVER_URL}"
agent_token: "${AGENT_TOKEN}"
interval: 15
command_log: "${CMD_LOG}"
state_file: "${STATE_DIR}/state.json"
auth_log_sources:
  - "/var/log/auth.log"
  - "/var/log/secure"
ssl_verify: true
timeout: 10
batch_size: 100
debug: false
CONF
chmod 640 "$CONFIG_DIR/config.yaml"
log "Config ditulis ke $CONFIG_DIR/config.yaml"

# ── Pasang bash hook ─────────────────────────────────────────────────────────
info "Memasang bash PROMPT_COMMAND hook..."

cat > "$HOOK_FILE" <<'HOOK'
# ServerAgent Monitor - bash command capture hook
# Jangan hapus file ini — digunakan untuk audit command

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
log "Hook dipasang: $HOOK_FILE"

# Pasang hook untuk root juga (tambahkan ke .bashrc root)
ROOT_BASHRC="/root/.bashrc"
if ! grep -q "_sa_capture" "$ROOT_BASHRC" 2>/dev/null; then
    echo "" >> "$ROOT_BASHRC"
    echo "# ServerAgent hook" >> "$ROOT_BASHRC"
    echo "[ -f $HOOK_FILE ] && source $HOOK_FILE" >> "$ROOT_BASHRC"
    log "Hook ditambahkan ke $ROOT_BASHRC"
fi

# Pasang juga ke /etc/bash.bashrc — file ini di-source bash untuk SEMUA shell
# interaktif (login MAUPUN non-login), beda dengan /etc/profile.d yang cuma
# untuk login shell. Ini menangkap kasus `su user` (tanpa '-') yang sebelumnya lolos.
SYS_BASHRC="/etc/bash.bashrc"
[[ -f "$SYS_BASHRC" ]] || SYS_BASHRC="/etc/bashrc"   # RHEL/CentOS pakai nama ini
if [[ -f "$SYS_BASHRC" ]] && ! grep -q "_sa_capture" "$SYS_BASHRC" 2>/dev/null; then
    echo "" >> "$SYS_BASHRC"
    echo "# ServerAgent hook — tangkap command dari su tanpa '-' (non-login interaktif)" >> "$SYS_BASHRC"
    echo "[ -f $HOOK_FILE ] && source $HOOK_FILE" >> "$SYS_BASHRC"
    log "Hook ditambahkan ke $SYS_BASHRC"
fi

# ── Set permission log file ──────────────────────────────────────────────────
touch "$CMD_LOG"
chmod 622 "$CMD_LOG"          # semua user bisa tulis, agent bisa baca
chmod 733 "$CMD_LOG_DIR"      # semua user bisa tulis ke direktori
chown "$AGENT_USER:$AGENT_USER" "$CMD_LOG" "$CMD_LOG_DIR" || true
log "Permission log file diset"

# Tambahkan user ke grup adm/systemd-journal untuk baca auth.log
usermod -aG adm "$AGENT_USER" 2>/dev/null || true
usermod -aG systemd-journal "$AGENT_USER" 2>/dev/null || true

# Set permission state dan config
chown -R "$AGENT_USER:$AGENT_USER" "$INSTALL_DIR" "$STATE_DIR" 2>/dev/null || true
chown root:"$AGENT_USER" "$CONFIG_DIR/config.yaml"
log "Permission set"

# Buat wrapper kill session (untuk fitur Kill Session dari web UI)
KILL_WRAPPER="/usr/local/bin/sa-kill-session"
cat > "$KILL_WRAPPER" <<'KILLSCRIPT'
#!/bin/bash
# Wrapper kill session untuk ServerAgent (dijalankan via sudo oleh agent)
# Usage: sa-kill-session <terminal> [pid]
TERMINAL="$1"
PID="$2"

if [[ -n "$PID" ]] && [[ "$PID" =~ ^[0-9]+$ ]]; then
    kill -9 "$PID" 2>/dev/null && exit 0
fi

if [[ -n "$TERMINAL" ]]; then
    pkill -KILL -t "$TERMINAL" 2>/dev/null && exit 0
    DEVPATH="/dev/$TERMINAL"
    [[ -e "$DEVPATH" ]] && fuser -k "$DEVPATH" 2>/dev/null && exit 0
fi

exit 1
KILLSCRIPT
chmod 755 "$KILL_WRAPPER"
chown root:root "$KILL_WRAPPER"
log "Wrapper kill session: $KILL_WRAPPER"

SUDOERS_FILE="/etc/sudoers.d/serveragent-kill"
cat > "$SUDOERS_FILE" <<EOF
Defaults:${AGENT_USER} !requiretty
${AGENT_USER} ALL=(ALL) NOPASSWD: $KILL_WRAPPER
EOF
chmod 440 "$SUDOERS_FILE"
log "Sudoers kill diset: $SUDOERS_FILE"

# ── Deteksi environment (LXC tidak support semua fitur systemd, dan TIDAK
#    bisa menjalankan auditd sama sekali — kernel audit netlink socket
#    tidak diekspos ke container unprivileged) ──────────────────────────────
IS_LXC=false
if systemd-detect-virt 2>/dev/null | grep -qi "lxc"; then
    IS_LXC=true
elif grep -qa "container=lxc" /proc/1/environ 2>/dev/null; then
    IS_LXC=true
fi

# ── Auditd rules (sumber terbaik untuk menangkap SEMUA user — shell non-bash,
#    sesi SSH non-interaktif, `su user` tanpa '-' — karena bekerja di level
#    kernel execve, bukan lewat shell). DILEWATI di LXC: auditd dipastikan
#    gagal start di container unprivileged Proxmox (Connection refused saat
#    bicara ke netlink audit), jadi capture di LXC mengandalkan bash hook saja.
if [[ "$IS_LXC" == "true" ]]; then
    info "LXC terdeteksi — auditd dilewati (tidak didukung di container unprivileged)."
    info "Command capture mengandalkan bash hook (/etc/profile.d + /etc/bash.bashrc)."
elif ! command -v auditctl &>/dev/null; then
    warn "auditctl tidak ditemukan — install paket auditd/audit gagal?"
    warn "Command dari shell non-bash / sesi SSH non-interaktif TIDAK akan tertangkap."
else
    cat > /etc/audit/rules.d/serveragent.rules <<'AUDIT'
# ServerAgent: tangkap semua eksekusi proses
-a always,exit -F arch=b64 -S execve -k cmd_exec
-a always,exit -F arch=b32 -S execve -k cmd_exec
AUDIT
    systemctl enable auditd 2>/dev/null || true
    systemctl restart auditd 2>/dev/null || service auditd restart 2>/dev/null || true
    if systemctl is-active --quiet auditd 2>/dev/null; then
        log "Auditd rules dipasang & service aktif"
    else
        warn "Auditd rules ditulis tapi service tidak aktif — cek: journalctl -u auditd"
    fi
fi

if [[ "$IS_LXC" == "true" ]]; then
    info "LXC container terdeteksi — menggunakan service tanpa namespace hardening"
    SECURITY_OPTS="NoNewPrivileges=yes"
else
    SECURITY_OPTS="NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ReadWritePaths=${STATE_DIR} ${CMD_LOG_DIR}
ReadOnlyPaths=/var/log /etc /home /root ${INSTALL_DIR}"
fi

# ── Systemd service ──────────────────────────────────────────────────────────
cat > "/etc/systemd/system/${SERVICE_NAME}.service" <<SVC
[Unit]
Description=ServerAgent Monitor Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${AGENT_USER}
Group=${AGENT_USER}
ExecStart=${INSTALL_DIR}/venv/bin/python3 ${INSTALL_DIR}/agent.py
WorkingDirectory=${INSTALL_DIR}
Restart=always
RestartSec=10
StartLimitIntervalSec=60
StartLimitBurst=3
StandardOutput=journal
StandardError=journal
SyslogIdentifier=${SERVICE_NAME}
EnvironmentFile=-${CONFIG_DIR}/env
${SECURITY_OPTS}

[Install]
WantedBy=multi-user.target
SVC

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"
sleep 3

# ── Verifikasi + tampilkan error jika gagal ───────────────────────────────────
echo ""
if systemctl is-active --quiet "$SERVICE_NAME"; then
    log "Service $SERVICE_NAME berjalan!"
else
    warn "Service tidak aktif — log terakhir:"
    journalctl -u "$SERVICE_NAME" -n 15 --no-pager 2>/dev/null || true
    echo ""
    warn "Coba jalankan manual untuk debug:"
    warn "  sudo -u ${AGENT_USER} ${INSTALL_DIR}/venv/bin/python3 ${INSTALL_DIR}/agent.py"
fi

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   Instalasi selesai!                                  ║${NC}"
echo -e "${GREEN}╠══════════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║${NC} Status   : systemctl status $SERVICE_NAME"
echo -e "${GREEN}║${NC} Log agent: journalctl -u $SERVICE_NAME -f"
echo -e "${GREEN}║${NC} Cmd log  : tail -f $CMD_LOG"
echo -e "${GREEN}╚══════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}PENTING: Source hook untuk sesi yang sudah berjalan:${NC}"
echo -e "  ${CYAN}source $HOOK_FILE${NC}"
echo ""
echo -e "${YELLOW}Atau buka sesi SSH baru — hook aktif otomatis.${NC}"
echo ""
