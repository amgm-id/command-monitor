#!/bin/bash
# ServerAgent Monitor - Update/Fix Agent di Semua CT Proxmox
# Jalankan di HOST PROXMOX
# Usage: bash proxmox_update.sh [--ct 100,101,105]
#
# Gunakan ini jika agent sudah terinstall tapi perlu update atau ada masalah.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CT_IDS="${1:-}"
SKIP_CONFIRM=false

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'
log()  { echo -e "${GREEN}[✓]${NC} $*"; }
info() { echo -e "${CYAN}[→]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }
err()  { echo -e "${RED}[✗]${NC} $*"; exit 1; }

# Parse args
while [[ $# -gt 0 ]]; do
    case $1 in
        --ct) CT_IDS="$2"; shift 2 ;;
        -y|--yes) SKIP_CONFIRM=true; shift ;;
        *) err "Unknown: $1" ;;
    esac
done

command -v pct &>/dev/null || err "Jalankan di host Proxmox!"
[[ -f "$SCRIPT_DIR/agent.py" ]]    || err "agent.py tidak ditemukan"
[[ -f "$SCRIPT_DIR/fix_agent.sh" ]] || err "fix_agent.sh tidak ditemukan"

# Daftar CT
ALL_RUNNING=$(pct list 2>/dev/null | awk 'NR>1 && $2=="running" {print $1}')
[[ -z "$ALL_RUNNING" ]] && err "Tidak ada CT running"

if [[ -n "$CT_IDS" ]]; then
    SELECTED=$(echo "$CT_IDS" | tr ',' '\n')
else
    SELECTED="$ALL_RUNNING"
fi

COUNT=$(echo "$SELECTED" | grep -c .)
echo ""
echo -e "${BOLD}CT yang akan di-update: $COUNT CT${NC}"
echo "$SELECTED" | while read -r ctid; do
    ct_hostname=$(pct exec "$ctid" -- hostname 2>/dev/null || echo "?")
    printf "  CT %-6s — %s\n" "$ctid" "$ct_hostname"
done
echo ""

if [[ "$SKIP_CONFIRM" != "true" ]]; then
    read -rp "Lanjutkan update? (y/N): " CONFIRM
    [[ "$CONFIRM" != "y" && "$CONFIRM" != "Y" ]] && { echo "Dibatalkan."; exit 0; }
fi

SUCCESS=0; FAILED=0
for ctid in $SELECTED; do
    echo ""
    echo -e "${BOLD}▶ CT $ctid${NC}"

    # Copy file terbaru
    pct push "$ctid" "$SCRIPT_DIR/agent.py"    /tmp/sa_agent.py    2>/dev/null
    pct push "$ctid" "$SCRIPT_DIR/fix_agent.sh" /tmp/sa_fix.sh     2>/dev/null

    # Jalankan fix
    pct exec "$ctid" -- bash -c "
        cp /tmp/sa_agent.py /opt/serveragent/agent.py 2>/dev/null || true
        chmod +x /tmp/sa_fix.sh
        bash /tmp/sa_fix.sh
        rm -f /tmp/sa_agent.py /tmp/sa_fix.sh
    " && {
        log "CT $ctid updated"
        SUCCESS=$((SUCCESS+1))
    } || {
        warn "CT $ctid gagal"
        FAILED=$((FAILED+1))
    }
done

echo ""
echo -e "${GREEN}Selesai: $SUCCESS berhasil${NC}${FAILED:+, }${FAILED:+${RED}$FAILED gagal${NC}}"
