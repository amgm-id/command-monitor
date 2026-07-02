from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    APP_NAME: str = "ServerAgent Monitor"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    DATABASE_URL: str = "postgresql://serveragent:serveragent123@localhost:5432/serveragent_db"
    ASYNC_DATABASE_URL: str = "postgresql+asyncpg://serveragent:serveragent123@localhost:5432/serveragent_db"

    SECRET_KEY: str = "change-this-to-a-very-long-random-secret-key-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 8  # 8 hours

    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:5173"]

    AGENT_TOKEN_LENGTH: int = 64

    REDIS_URL: str = "redis://localhost:6379"

    HIGH_RISK_COMMANDS: list[str] = [
        "rm -rf", "rm -fr", "chmod 777", "chmod -R 777",
        "useradd", "userdel", "usermod", "passwd",
        "systemctl stop", "systemctl disable", "service stop",
        "iptables", "ufw disable", "ufw reset",
        "docker stop", "docker rm", "docker rmi", "docker system prune",
        "dd if=", "mkfs", "fdisk", "parted",
        ">/etc/passwd", ">/etc/shadow",
        "crontab", "at ", "nohup",
        "curl | bash", "wget | bash", "curl | sh", "wget | sh",
        "nc -l", "netcat -l",
        "python -c", "perl -e", "ruby -e",
        "base64 -d", "eval ",
        "shutdown", "reboot", "halt", "poweroff",
        "kill -9", "killall",
        "export PATH=", "export LD_",
        "sudo su", "sudo -i", "sudo bash",
        "chattr", "lsattr",
        "visudo", "sudoers",
    ]

    MEDIUM_RISK_COMMANDS: list[str] = [
        "systemctl restart", "service restart",
        "apt install", "apt remove", "apt purge",
        "yum install", "yum remove", "dnf install",
        "pip install", "npm install -g",
        "chmod 755", "chmod 644",
        "chown", "chgrp",
        "ssh-keygen", "ssh-copy-id",
        "mysql", "psql", "mongodump",
        "tar -x", "unzip", "gunzip",
        "wget ", "curl -O", "curl -o",
        "git clone", "git pull",
        "docker run", "docker pull", "docker-compose",
        "crontab -e",
    ]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
