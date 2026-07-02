#!/bin/bash
# ServerAgent bash hook — dipasang di /etc/profile.d/serveragent_hook.sh
# Menangkap setiap command yang dijalankan secara real-time.
# File ini di-source otomatis oleh bash untuk setiap sesi login baru.

_SA_LOG="/var/log/serveragent/commands.log"

_sa_capture() {
    local _ec=$?   # HARUS baris pertama — tangkap exit code sebelum apapun
    local _cmd

    # Baca command terakhir dari in-memory history (tanpa timestamp prefix)
    _cmd=$(HISTTIMEFORMAT='' history 1 2>/dev/null | sed 's/^[[:space:]]*[0-9][0-9]*[[:space:]]*//')

    # Abaikan jika kosong atau sama dengan command sebelumnya
    [ -z "$_cmd" ] && return $_ec
    [ "$_cmd" = "$_SA_LAST_CMD" ] && return $_ec
    _SA_LAST_CMD="$_cmd"

    # Tulis ke log: timestamp|user|remote_ip|terminal|working_dir|exit_code|command
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

# Aktifkan history append per-command (flush langsung ke file)
shopt -s histappend 2>/dev/null
HISTCONTROL=ignoredups
HISTSIZE=50000
HISTFILESIZE=100000

# Pasang hook — letakkan DI DEPAN agar exit code selalu tepat
if [[ "$PROMPT_COMMAND" != *"_sa_capture"* ]]; then
    PROMPT_COMMAND="_sa_capture${PROMPT_COMMAND:+; $PROMPT_COMMAND}"
fi
