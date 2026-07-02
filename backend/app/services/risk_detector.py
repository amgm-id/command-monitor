from typing import Tuple
from app.config import get_settings
from app.models.command_log import RiskLevel

settings = get_settings()


def detect_risk(command: str) -> Tuple[RiskLevel, str]:
    """Analyze a command and return (risk_level, reason)."""
    cmd_lower = command.lower().strip()

    for pattern in settings.HIGH_RISK_COMMANDS:
        if pattern.lower() in cmd_lower:
            if any(p in cmd_lower for p in ["rm -rf /", "rm -fr /", "dd if=/dev/zero", "mkfs /dev/sd"]):
                return RiskLevel.CRITICAL, f"Extremely destructive command detected: matches pattern '{pattern}'"
            return RiskLevel.HIGH, f"High-risk command detected: matches pattern '{pattern}'"

    for pattern in settings.MEDIUM_RISK_COMMANDS:
        if pattern.lower() in cmd_lower:
            return RiskLevel.MEDIUM, f"Medium-risk command detected: matches pattern '{pattern}'"

    # Additional heuristic checks
    if _has_pipe_to_shell(cmd_lower):
        return RiskLevel.HIGH, "Piping content directly to shell interpreter (code injection risk)"

    if _is_privilege_escalation(cmd_lower):
        return RiskLevel.HIGH, "Potential privilege escalation attempt"

    if _has_suspicious_encoding(cmd_lower):
        return RiskLevel.MEDIUM, "Command uses encoding/obfuscation techniques"

    return RiskLevel.LOW, ""


def _has_pipe_to_shell(cmd: str) -> bool:
    shell_interpreters = ["bash", "sh", "zsh", "fish", "ksh", "python", "perl", "ruby"]
    if "|" in cmd:
        for interp in shell_interpreters:
            if f"| {interp}" in cmd or f"|{interp}" in cmd:
                return True
    return False


def _is_privilege_escalation(cmd: str) -> bool:
    patterns = [
        "sudo su", "sudo -i", "sudo bash", "sudo sh",
        "pkexec", "sudo -s",
    ]
    return any(p in cmd for p in patterns)


def _has_suspicious_encoding(cmd: str) -> bool:
    patterns = ["base64", "xxd", "od -", "printf '\\x", "echo -e '\\x"]
    return any(p in cmd for p in patterns)


def is_alert_worthy(risk_level: RiskLevel) -> bool:
    return risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)
