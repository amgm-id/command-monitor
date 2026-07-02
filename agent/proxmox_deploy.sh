#!/bin/bash
# ServerAgent Monitor - Proxmox Mass Deploy
# Jalankan di HOST PROXMOX (bukan di dalam CT)
# Usage: bash proxmox_deploy.sh --server http://SERVER:8888 --api-user admin --api-pass PASSWORD

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_URL=""
API_USER="admin"
API_PASS=""
CT_IDS=""
INTERVAL=15
SSL_VERIFY="true"
SKIP_CONFIRM=false
DEBUG=false

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'
BOLD='\033[1m'; NC='\033[0m'
# Semua output diagnostic ke stderr agar tidak mencemari command substitution $()
log()    { echo -e "${GREEN}[✓]${NC} $*" >&2; }
info()   { echo -e "${CYAN}[→]${NC} $*" >&2; }
warn()   { echo -e "${YELLOW}[!]${NC} $*" >&2; }
err()    { echo -e "${RED}[✗] ERROR: $*${NC}" >&2; exit 1; }
debug()  { [[ "$DEBUG" == "true" ]] && echo -e "${YELLOW}[D]${NC} $*" >&2 || true; }
header() { echo -e "\n${BOLD}${CYAN}── $* ──${NC}" >&2; }

while [[ $# -gt 0 ]]; do
    case $1 in
        --server)        SERVER_URL="${2%/}"; shift 2 ;;
        --api-user)      API_USER="$2"; shift 2 ;;
        --api-pass)      API_PASS="$2"; shift 2 ;;
        --ct)            CT_IDS="$2"; shift 2 ;;
        --interval)      INTERVAL="$2"; shift 2 ;;
        --no-ssl-verify) SSL_VERIFY="false"; shift ;;
        --debug)         DEBUG=true; shift ;;
        -y|--yes)        SKIP_CONFIRM=true; shift ;;
        -h|--help)
            echo "Usage: bash proxmox_deploy.sh --server URL --api-user USER --api-pass PASS [options]"
            echo "  --server URL        URL server pusat (misal: http://192.168.1.10:8888)"
            echo "  --api-user USER     Username login ServerAgent (default: admin)"
            echo "  --api-pass PASS     Password login ServerAgent"
            echo "  --ct IDs            CT ID pisah koma, misal: 100,101,105 (default: semua)"
            echo "  --interval N        Interval agent detik (default: 15)"
            echo "  --no-ssl-verify     Nonaktifkan SSL verify"
            echo "  --debug             Tampilkan response API mentah"
            echo "  -y                  Skip konfirmasi"
            exit 0 ;;
        *) err "Unknown argument: $1. Gunakan --help untuk panduan." ;;
    esac
done

[[ -z "$SERVER_URL" ]] && err "Butuh --server URL"
[[ -z "$API_PASS" ]]   && err "Butuh --api-pass PASSWORD"
command -v pct    &>/dev/null || err "Perintah 'pct' tidak ditemukan — jalankan di host Proxmox!"
command -v curl   &>/dev/null || err "curl tidak ditemukan"
command -v python3 &>/dev/null || err "python3 tidak ditemukan"
[[ -f "$SCRIPT_DIR/agent.py" ]]   || err "agent.py tidak ditemukan di $SCRIPT_DIR"
[[ -f "$SCRIPT_DIR/install.sh" ]] || err "install.sh tidak ditemukan di $SCRIPT_DIR"

# ── Wrapper curl yang aman (tidak ada -f, selalu follow redirect) ─────────────
# Usage: api_call METHOD ENDPOINT [BODY]
# Returns: 0 jika 2xx, 1 jika error
# Sets: _RESP (body), _HTTP (status code)
api_call() {
    local method="$1"
    local endpoint="$2"
    local body="${3:-}"
    local url="${SERVER_URL}${endpoint}"
    local tmpfile
    tmpfile=$(mktemp)

    local curl_args=(-s -L --max-time 15 -o "$tmpfile" -w "%{http_code}")
    [[ "$SSL_VERIFY" == "false" ]] && curl_args+=(-k)

    if [[ -n "$body" ]]; then
        curl_args+=(-X "$method" -H "Content-Type: application/json" -d "$body")
    else
        curl_args+=(-X "$method")
    fi

    [[ -n "${JWT:-}" ]] && curl_args+=(-H "Authorization: Bearer $JWT")

    debug "curl ${method} ${url}"
    _HTTP=$(curl "${curl_args[@]}" "$url" 2>/dev/null) || {
        _RESP="curl connection error"
        _HTTP="000"
        rm -f "$tmpfile"
        return 1
    }
    _RESP=$(cat "$tmpfile")
    rm -f "$tmpfile"

    debug "HTTP $_HTTP | body: ${_RESP:0:200}"

    if [[ "$_HTTP" =~ ^2 ]]; then
        return 0
    else
        return 1
    fi
}

# ── Login ─────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${CYAN}╔══════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${CYAN}║   ServerAgent Monitor - Proxmox Deploy   ║${NC}"
echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════╝${NC}"
echo ""
info "Server  : $SERVER_URL"
info "API user: $API_USER"
echo ""

header "Login ke ServerAgent"

LOGIN_BODY="{\"username\":\"${API_USER}\",\"password\":\"${API_PASS}\"}"
if ! api_call POST "/api/auth/login" "$LOGIN_BODY"; then
    echo -e "${RED}[✗] Login gagal (HTTP $_HTTP)${NC}"
    echo "Response: $_RESP"
    echo ""
    echo "Pastikan:"
    echo "  1. URL benar: $SERVER_URL"
    echo "  2. Username/password benar"
    echo "  3. Server pusat bisa diakses dari host Proxmox ini"
    echo "     Test: curl -v $SERVER_URL/api/auth/login"
    exit 1
fi

JWT=$(echo "$_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['access_token'])" 2>/dev/null)
if [[ -z "$JWT" ]]; then
    echo -e "${RED}[✗] Gagal ambil access_token dari response${NC}"
    echo "Response: $_RESP"
    exit 1
fi
log "Login berhasil"

# ── Ambil daftar CT ───────────────────────────────────────────────────────────
header "Daftar Container Proxmox"

mapfile -t ALL_RUNNING < <(pct list 2>/dev/null | awk 'NR>1 && $2=="running" {print $1}')
if [[ ${#ALL_RUNNING[@]} -eq 0 ]]; then
    err "Tidak ada CT yang sedang running"
fi

if [[ -n "$CT_IDS" ]]; then
    mapfile -t REQUESTED < <(echo "$CT_IDS" | tr ',' '\n' | tr -d ' ')
    SELECTED=()
    for ctid in "${REQUESTED[@]}"; do
        if printf '%s\n' "${ALL_RUNNING[@]}" | grep -qx "$ctid"; then
            SELECTED+=("$ctid")
        else
            warn "CT $ctid tidak running — dilewati"
        fi
    done
else
    SELECTED=("${ALL_RUNNING[@]}")
fi

[[ ${#SELECTED[@]} -eq 0 ]] && err "Tidak ada CT valid untuk di-deploy"

# Kumpulkan info tiap CT
echo ""
declare -a CT_DATA
printf "${BOLD}%-8s %-22s %-16s %-18s %-12s${NC}\n" "CTID" "HOSTNAME" "IP" "NAMA SERVER" "OS"
printf "%-8s %-22s %-16s %-18s %-12s\n" "────" "────────" "──" "───────────" "──"

for ctid in "${SELECTED[@]}"; do
    CT_HOSTNAME=$(pct exec "$ctid" -- hostname 2>/dev/null | tr -d '\r\n' || echo "ct-${ctid}")
    CT_IP=$(pct exec "$ctid" -- hostname -I 2>/dev/null | awk '{print $1}' || echo "0.0.0.0")
    CT_OS=$(pct exec "$ctid" -- sh -c 'grep "^ID=" /etc/os-release 2>/dev/null | cut -d= -f2 | tr -d "\"" || echo "linux"')
    # Format nama: 2 oktet terakhir IP + hostname (misal: 10.10.222.5 + hrd → "222.5-hrd")
    CT_LABEL=$(echo "$CT_IP" | awk -F. '{print $3"."$4}')-${CT_HOSTNAME}
    printf "%-8s %-22s %-16s %-18s %-12s\n" "$ctid" "$CT_HOSTNAME" "$CT_IP" "$CT_LABEL" "$CT_OS"
    CT_DATA+=("${ctid}|${CT_HOSTNAME}|${CT_IP}|${CT_OS}|${CT_LABEL}")
done
echo ""

if [[ "$SKIP_CONFIRM" != "true" ]]; then
    read -rp "Deploy ke ${#CT_DATA[@]} CT di atas? (y/N): " CONFIRM
    [[ "$CONFIRM" != "y" && "$CONFIRM" != "Y" ]] && { echo "Dibatalkan."; exit 0; }
fi

# ── Fungsi: daftarkan 1 server ke API (selalu buat baru) ─────────────────────
# Args: $1=label, $2=hostname, $3=ip
# PENTING: hanya echo token ke stdout — semua pesan lain ke stderr via warn/info
register_server_api() {
    local label="$1"
    local hostname="$2"
    local ip="$3"
    local token=""

    # Hapus registrasi lama jika ada (agar token baru dibuat)
    if api_call GET "/api/servers/"; then
        local old_id
        old_id=$(echo "$_RESP" | python3 -c "
import sys, json
try:
    for s in json.load(sys.stdin):
        # Cocokkan hanya via name atau ip_address.
        # Jangan cocokkan via hostname: beberapa CT bisa punya hostname sama.
        if (s.get('name') == sys.argv[1]
                or s.get('ip_address') == sys.argv[3]):
            print(s['id'], end='')
            break
except Exception:
    pass
" "$label" "$hostname" "$ip" 2>/dev/null)
        if [[ -n "$old_id" ]]; then
            info "Server '$label' sudah ada (id=$old_id), hapus & daftar ulang..." >&2
            api_call DELETE "/api/servers/${old_id}" || true
        fi
    fi

    # Buat server baru → token baru
    local body
    body=$(python3 -c "
import json, sys
print(json.dumps({
    'name': sys.argv[1],
    'hostname': sys.argv[2],
    'ip_address': sys.argv[3],
    'description': 'CT Proxmox - auto-registered'
}), end='')
" "$label" "$hostname" "$ip" 2>/dev/null)

    if ! api_call POST "/api/servers/" "$body"; then
        warn "Gagal buat server '$hostname' (HTTP $_HTTP)" >&2
        debug "Response: $_RESP"
        return 1
    fi

    token=$(echo "$_RESP" | python3 -c "
import sys, json
try:
    print(json.load(sys.stdin)['agent_token'], end='')
except Exception as e:
    print(f'ERROR: {e}', file=sys.stderr)
" 2>/dev/null)

    if [[ -z "$token" ]]; then
        warn "Gagal ambil agent_token (HTTP $_HTTP): ${_RESP:0:150}" >&2
        return 1
    fi

    token=$(printf '%s' "$token" | tr -cd '[:alnum:]_-')

    if [[ ${#token} -lt 10 ]]; then
        warn "Token tidak valid setelah sanitasi: '$token'" >&2
        return 1
    fi

    printf '%s' "$token"
    return 0
}

# ── Fungsi: update token di config yang sudah ada (tanpa full reinstall) ──────
update_token_only() {
    local ctid="$1"
    local token="$2"
    local server_url="$3"
    local agent_py="$4"   # path file agent.py lokal untuk di-push

    pct push "$ctid" "$agent_py" /opt/serveragent/agent.py 2>/dev/null || {
        warn "Gagal update agent.py di CT $ctid" >&2; return 1
    }

    # Tulis ulang config.yaml dengan token baru
    pct exec "$ctid" -- bash -c "
cat > /etc/serveragent/config.yaml << 'YAMLEOF'
server_url: \"${server_url}\"
agent_token: \"${token}\"
interval: ${INTERVAL}
command_log: /var/log/serveragent/commands.log
state_file: /var/lib/serveragent/state.json
auth_log_sources:
  - /var/log/auth.log
  - /var/log/secure
ssl_verify: true
timeout: 10
batch_size: 100
debug: false
YAMLEOF
chmod 640 /etc/serveragent/config.yaml
" 2>/dev/null || { warn "Gagal update config di CT $ctid" >&2; return 1; }

    # Reset state agar agent baca ulang dari awal
    pct exec "$ctid" -- bash -c "
python3 -c \"
import json, os
p='/var/lib/serveragent/state.json'
if os.path.exists(p):
    s=json.loads(open(p).read())
    s.pop('hook_log_pos',None)
    open(p,'w').write(json.dumps(s))
\" 2>/dev/null || true
" 2>/dev/null || true

    # Restart service
    pct exec "$ctid" -- systemctl restart serveragent 2>/dev/null || {
        warn "Gagal restart service di CT $ctid" >&2; return 1
    }
    return 0
}

# ── Deploy ke tiap CT ─────────────────────────────────────────────────────────
header "Mulai Deploy"
SUCCESS=0
FAILED=0
declare -a FAILED_CTS

for CT_ENTRY in "${CT_DATA[@]}"; do
    IFS='|' read -r ctid ct_hostname ct_ip ct_os ct_label <<< "$CT_ENTRY"

    echo "" >&2
    echo -e "${BOLD}▶ CT ${ctid}  ${ct_label} (${ct_ip})${NC}" >&2

    # 1. Daftarkan — kirim label sebagai nama, hostname dan IP sebagai identifier
    info "Mendaftarkan '$ct_label' ke server pusat..."
    AGENT_TOKEN=$(register_server_api "$ct_label" "$ct_hostname" "$ct_ip") || {
        warn "Gagal mendaftarkan CT $ctid — dilewati"
        FAILED=$((FAILED+1)); FAILED_CTS+=("$ctid"); continue
    }
    # Sanitasi: buang semua karakter non-alfanumerik (ANSI codes, newline, spasi)
    AGENT_TOKEN=$(printf '%s' "$AGENT_TOKEN" | tr -cd '[:alnum:]_-')
    if [[ ${#AGENT_TOKEN} -lt 10 ]]; then
        warn "Token tidak valid untuk CT $ctid ('${AGENT_TOKEN}') — dilewati"
        FAILED=$((FAILED+1)); FAILED_CTS+=("$ctid"); continue
    fi
    log "Token: ${AGENT_TOKEN:0:20}... (${#AGENT_TOKEN} chars)"

    # 2. Cek apakah agent sudah terinstall (venv ada = pernah install sebelumnya)
    ALREADY_INSTALLED=false
    if pct exec "$ctid" -- test -f /opt/serveragent/venv/bin/python3 2>/dev/null; then
        ALREADY_INSTALLED=true
    fi

    if [[ "$ALREADY_INSTALLED" == "true" ]]; then
        # ── Jalur cepat: cukup update token + agent.py + restart ──────────────
        info "Agent sudah terinstall — update token & restart..."
        if update_token_only "$ctid" "$AGENT_TOKEN" "$SERVER_URL" "$SCRIPT_DIR/agent.py"; then
            log "Token diperbarui, service di-restart ✓"
            SUCCESS=$((SUCCESS+1))
        else
            warn "Update token gagal di CT $ctid"
            FAILED=$((FAILED+1)); FAILED_CTS+=("$ctid")
        fi
    else
        # ── Jalur penuh: fresh install ─────────────────────────────────────────
        pct exec "$ctid" -- sh -c "mkdir -p /tmp/_sa_install" 2>/dev/null || true

        info "Mengcopy file ke CT..."
        if ! pct push "$ctid" "$SCRIPT_DIR/agent.py"   /tmp/_sa_install/agent.py   2>/dev/null; then
            warn "Gagal push agent.py ke CT $ctid"
            FAILED=$((FAILED+1)); FAILED_CTS+=("$ctid"); continue
        fi
        if ! pct push "$ctid" "$SCRIPT_DIR/install.sh" /tmp/_sa_install/install.sh 2>/dev/null; then
            warn "Gagal push install.sh ke CT $ctid"
            FAILED=$((FAILED+1)); FAILED_CTS+=("$ctid"); continue
        fi
        log "File tercopy"

        info "Menjalankan full install di CT $ctid..."
        INSTALL_LOG=$(pct exec "$ctid" -- bash -c "
            chmod +x /tmp/_sa_install/install.sh
            bash /tmp/_sa_install/install.sh \
                --server '${SERVER_URL}' \
                --token '${AGENT_TOKEN}' 2>&1
        " 2>&1) && INSTALL_OK=true || INSTALL_OK=false

        if [[ "$INSTALL_OK" == "true" ]]; then
            log "Agent terinstall di CT $ctid"
            [[ "$DEBUG" == "true" ]] && echo "$INSTALL_LOG"
            SUCCESS=$((SUCCESS+1))
        else
            warn "Install gagal di CT $ctid"
            echo "$INSTALL_LOG" | tail -10
            FAILED=$((FAILED+1)); FAILED_CTS+=("$ctid")
        fi

        pct exec "$ctid" -- rm -rf /tmp/_sa_install 2>/dev/null || true
    fi
done

# ── Ringkasan ─────────────────────────────────────────────────────────────────
header "Ringkasan"
echo ""
echo -e "  ${GREEN}Berhasil : ${SUCCESS} CT${NC}"
[[ $FAILED -gt 0 ]] && echo -e "  ${RED}Gagal    : ${FAILED} CT  →  ${FAILED_CTS[*]}${NC}"
echo ""

if [[ $SUCCESS -gt 0 ]]; then
    echo -e "${GREEN}Deploy selesai!${NC} Buka dashboard → Servers untuk melihat CT yang baru."
    echo ""
    echo -e "${YELLOW}Catatan:${NC} Hook bash aktif otomatis untuk sesi SSH baru di tiap CT."
    echo "Untuk sesi yang sedang terbuka:"
    echo -e "  ${CYAN}source /etc/profile.d/serveragent_hook.sh${NC}"
fi

if [[ $FAILED -gt 0 ]]; then
    echo ""
    echo -e "${YELLOW}Debug CT yang gagal:${NC}"
    for failed_ct in "${FAILED_CTS[@]}"; do
        echo -e "  ${CYAN}pct exec $failed_ct -- journalctl -u serveragent -n 20${NC}"
    done
    echo ""
    echo "Coba ulang manual:"
    echo -e "  ${CYAN}bash proxmox_deploy.sh --server $SERVER_URL --api-user $API_USER --api-pass '***' --ct $(IFS=,; echo "${FAILED_CTS[*]}") -y${NC}"
fi
echo ""
