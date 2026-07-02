# ServerAgent Monitor — Installation Guide

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Admin Browser  ──►  Web Dashboard (React)                  │
│                           │                                  │
│                           ▼ HTTP/WebSocket                   │
│                    Backend API (FastAPI)                      │
│                           │                                  │
│                           ▼                                  │
│                    PostgreSQL Database                        │
│                           ▲                                  │
│                     HTTPS / Token                            │
│  Server A  ──►  Agent (Python)                              │
│  Server B  ──►  Agent (Python)                              │
│  Server N  ──►  Agent (Python)                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Option 1: Docker Compose (Recommended for Central Server)

### Prerequisites
- Docker >= 24.x
- Docker Compose v2
- Port 80 and 8000 available

### Steps

```bash
# Clone the project
git clone https://github.com/yourorg/serveragent-monitor.git
cd serveragent-monitor

# Generate a secret key
python3 -c "import secrets; print(secrets.token_hex(32))"

# Create environment file
cp .env.example .env
# Edit .env and set SECRET_KEY to the generated value

# Build and start all services
docker-compose up -d

# Check status
docker-compose ps
docker-compose logs -f backend

# Access web dashboard
# → http://your-server-ip
# Default credentials: admin / Admin@1234
# CHANGE THE PASSWORD IMMEDIATELY after first login!
```

---

## Option 2: Manual Installation (Central Server)

### 2.1 PostgreSQL

```bash
# Debian/Ubuntu
sudo apt install -y postgresql postgresql-contrib
sudo -u postgres psql <<SQL
CREATE USER serveragent WITH PASSWORD 'strong_password_here';
CREATE DATABASE serveragent_db OWNER serveragent;
GRANT ALL PRIVILEGES ON DATABASE serveragent_db TO serveragent;
SQL
```

```bash
# RHEL/Rocky
sudo dnf install -y postgresql-server postgresql-contrib
sudo postgresql-setup --initdb
sudo systemctl enable --now postgresql
sudo -u postgres psql <<SQL
CREATE USER serveragent WITH PASSWORD 'strong_password_here';
CREATE DATABASE serveragent_db OWNER serveragent;
GRANT ALL PRIVILEGES ON DATABASE serveragent_db TO serveragent;
SQL
```

### 2.2 Backend (FastAPI)

```bash
cd /opt
sudo git clone https://github.com/yourorg/serveragent-monitor.git
sudo chown -R www-data: serveragent-monitor/backend

cd serveragent-monitor/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create .env
cat > .env <<ENV
DATABASE_URL=postgresql://serveragent:strong_password_here@localhost:5432/serveragent_db
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
ALLOWED_ORIGINS=["https://yourdomain.com"]
DEBUG=false
ENV

# Start backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

**Systemd service** (`/etc/systemd/system/serveragent-backend.service`):
```ini
[Unit]
Description=ServerAgent Backend
After=network.target postgresql.service

[Service]
User=www-data
WorkingDirectory=/opt/serveragent-monitor/backend
ExecStart=/opt/serveragent-monitor/backend/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always
EnvironmentFile=/opt/serveragent-monitor/backend/.env

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now serveragent-backend
```

### 2.3 Frontend (React/Vite)

```bash
cd /opt/serveragent-monitor/frontend
npm ci
npm run build
# Serve dist/ directory with nginx
```

**Nginx config** (`/etc/nginx/sites-available/serveragent`):
```nginx
server {
    listen 80;
    server_name yourdomain.com;
    root /opt/serveragent-monitor/frontend/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location /ws {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/serveragent /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

---

## Option 3: Install Agent on Monitored Servers

### Step 1: Add the server in the web dashboard
1. Login to dashboard → **Servers** → **Add Server**
2. Fill in name, hostname, IP
3. **Copy the Agent Token** from the server card

### Step 2: Run the installer on the target server

```bash
# Transfer agent files to the target server
scp -r agent/ user@192.168.1.10:/tmp/serveragent-agent/

# SSH into the target server and run the installer
ssh user@192.168.1.10
sudo bash /tmp/serveragent-agent/install.sh \
    --server https://your-central-server.com \
    --token "PASTE_YOUR_AGENT_TOKEN_HERE"
```

### Step 3: Enable advanced auditd tracking (recommended)

```bash
# On the monitored server, after install.sh
sudo bash /tmp/serveragent-agent/audit_setup.sh
```

### Step 4: Verify

```bash
# Check agent is running
sudo systemctl status serveragent

# Watch live logs
sudo journalctl -u serveragent -f

# Verify data is arriving in dashboard
# Open the web dashboard → Dashboard → Recent Commands
```

---

## Manual Agent Configuration

Edit `/etc/serveragent/config.yaml`:

```yaml
server_url: "https://your-central-server.com"
agent_token: "YOUR_UNIQUE_TOKEN_HERE"
interval: 30          # seconds (min 15)
ssl_verify: true      # set false ONLY for self-signed certs in dev
debug: false
```

---

## API Endpoints Reference

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/login` | Login, returns JWT token |
| POST | `/api/auth/logout` | Logout |
| GET  | `/api/auth/me` | Get current user info |

### Dashboard
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/dashboard/stats` | Summary statistics |
| GET | `/api/dashboard/activity-chart?period=24h` | Activity chart data |
| GET | `/api/dashboard/risk-distribution` | Risk level breakdown |

### Command Logs
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/command-logs/` | List with filters & pagination |
| GET | `/api/command-logs/export/csv` | Export as CSV |
| GET | `/api/command-logs/export/excel` | Export as Excel |
| GET | `/api/command-logs/export/pdf` | Export as PDF |

### Sessions
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/sessions/active` | Active sessions |
| GET | `/api/sessions/history` | Login history |
| GET | `/api/sessions/history/export/{format}` | Export session history |

### Alerts
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/alerts/` | List alerts |
| GET | `/api/alerts/unread-count` | Unacknowledged count |
| POST | `/api/alerts/{id}/acknowledge` | Acknowledge single alert |
| POST | `/api/alerts/acknowledge-bulk` | Acknowledge multiple |

### Servers
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/servers/` | List all servers |
| POST | `/api/servers/` | Register new server |
| GET | `/api/servers/{id}` | Server details |
| PUT | `/api/servers/{id}` | Update server |
| POST | `/api/servers/{id}/rotate-token` | Rotate agent token |

### Agent (authenticated by X-Agent-Token header)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/agent/heartbeat` | Agent keepalive |
| POST | `/api/agent/commands` | Ingest command batch |
| POST | `/api/agent/sessions` | Ingest session data |

---

## Role-Based Access Control

| Permission | Super Admin | Admin | Auditor | Viewer |
|------------|-------------|-------|---------|--------|
| View dashboard | ✅ | ✅ | ✅ | ✅ |
| View commands | ✅ | ✅ | ✅ | ✅ |
| Export data | ✅ | ✅ | ✅ | ✅ |
| Acknowledge alerts | ✅ | ✅ | ✅ | ❌ |
| Manage servers | ✅ | ✅ | ❌ | ❌ |
| Rotate agent tokens | ✅ | ✅ | ❌ | ❌ |
| Manage users | ✅ | ✅ | ❌ | ❌ |
| Create super admin | ✅ | ❌ | ❌ | ❌ |

---

## Security Hardening

### Central Server
```bash
# Use HTTPS (Let's Encrypt)
sudo certbot --nginx -d yourdomain.com

# Firewall: only allow 80/443 + 22 from trusted IPs
sudo ufw allow 22
sudo ufw allow 80
sudo ufw allow 443
sudo ufw enable

# Change the default admin password after first login!
```

### Agent Security
- Each server gets a unique, random 64-character agent token
- Communication is HTTPS-only (set ssl_verify: true)
- Agent runs as non-root `serveragent` user
- Token rotation available from the dashboard
- Log data is write-only (no delete API)

### Database Backup
```bash
# Daily backup cron
echo "0 2 * * * pg_dump -U serveragent serveragent_db | gzip > /backup/serveragent_\$(date +%Y%m%d).sql.gz" | crontab -

# Docker backup
docker exec serveragent_db pg_dump -U serveragent serveragent_db | gzip > backup.sql.gz
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Agent can't connect | Check `server_url` and firewall on central server |
| SSL error | Check certificate or set `ssl_verify: false` for self-signed |
| No commands showing | Ensure auditd is running and agent has read permission to logs |
| Token invalid | Rotate token in dashboard and update agent config |
| High memory usage | Increase `interval`, reduce `batch_size` |
| Missing commands | Source `/etc/profile.d/serveragent_history.sh` in users' shells |

```bash
# Agent diagnostic
sudo journalctl -u serveragent --since "1 hour ago"

# Test API connection manually
curl -H "X-Agent-Token: YOUR_TOKEN" https://your-server.com/api/agent/heartbeat \
     -X POST -H "Content-Type: application/json" \
     -d '{"hostname":"test","ip_address":"1.2.3.4","timestamp":"2024-01-01T00:00:00Z"}'
```
