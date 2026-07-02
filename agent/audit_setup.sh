#!/bin/bash
# Advanced auditd setup for comprehensive command logging
# Run as root after installing auditd

set -e

RULES_FILE="/etc/audit/rules.d/99-serveragent-full.rules"

cat > "$RULES_FILE" <<'RULES'
# Delete all existing rules
-D

# Increase buffer size
-b 8192

# Fail on error (0=silent, 1=printk, 2=panic)
-f 1

# Track all executions (primary command source)
-a always,exit -F arch=b64 -S execve -k cmd_exec
-a always,exit -F arch=b32 -S execve -k cmd_exec

# Track file permission changes
-a always,exit -F arch=b64 -S chmod,fchmod,fchmodat -k file_perm
-a always,exit -F arch=b64 -S chown,fchown,fchownat -k file_owner

# Track sensitive file access
-w /etc/passwd -p wa -k sensitive_files
-w /etc/shadow -p wa -k sensitive_files
-w /etc/sudoers -p wa -k sensitive_files
-w /etc/sudoers.d/ -p wa -k sensitive_files
-w /etc/ssh/sshd_config -p wa -k sensitive_files
-w /etc/crontab -p wa -k cron_change
-w /etc/cron.d/ -p wa -k cron_change
-w /var/spool/cron/ -p wa -k cron_change

# Track user/group management
-w /usr/sbin/useradd -p x -k user_mgmt
-w /usr/sbin/userdel -p x -k user_mgmt
-w /usr/sbin/usermod -p x -k user_mgmt
-w /usr/sbin/groupadd -p x -k user_mgmt
-w /usr/bin/passwd -p x -k passwd_change

# Track network config changes
-w /etc/network/ -p wa -k net_config
-w /etc/hosts -p wa -k net_config

# Track module loading
-a always,exit -F arch=b64 -S init_module,finit_module -k module_load
-w /sbin/insmod -p x -k module_load
-w /sbin/rmmod -p x -k module_load

# Track privilege escalation
-w /bin/su -p x -k priv_escalation
-w /usr/bin/sudo -p x -k priv_escalation

# Make config immutable (requires reboot to change)
# Uncomment in production:
# -e 2
RULES

# Load rules
auditctl -R "$RULES_FILE" 2>/dev/null || true
systemctl restart auditd

# Configure audisp syslog plugin to also write to syslog
AUDISP_SYSLOG="/etc/audisp/plugins.d/syslog.conf"
if [ -f "$AUDISP_SYSLOG" ]; then
    sed -i 's/^active = no/active = yes/' "$AUDISP_SYSLOG"
    systemctl restart auditd
fi

echo "✅ Auditd configured for full command tracking"
echo "   Rules file: $RULES_FILE"
echo "   Test with: ausearch -k cmd_exec | head -50"
