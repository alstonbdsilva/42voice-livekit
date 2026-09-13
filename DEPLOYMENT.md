# 🚀 42Voice - Hostinger VPS Multi-Domain Deployment Guide

Complete step-by-step guide for deploying **42Voice** on a **Hostinger VPS** using **Docker Compose**, multi-subdomain SSL proxying via **Caddy**, and **Supabase PostgreSQL**.

---

## 🌐 Subdomain Architecture

Your production stack is configured to run on 3 dedicated subdomains:

| Subdomain | Purpose | Target Service |
|---|---|---|
| `dashboard.42voice.com` | Web Application UI | `fe:80` (React SPA) |
| `api.42voice.com` | REST API Backend | `backend:8000` (FastAPI) |
| `ws.42voice.com` | LiveKit SFU WebRTC / WSS | `livekit:7880` (LiveKit Server) |

---

## 📋 Step 1: Set Up Hostinger / Cloudflare DNS A-Records

Point the following **3 DNS A-Records** to your **Hostinger VPS Public IP**:

| Type | Name / Host | Value / Target IP |
|---|---|---|
| **A Record** | `dashboard` | `<YOUR_HOSTINGER_VPS_IP>` |
| **A Record** | `api` | `<YOUR_HOSTINGER_VPS_IP>` |
| **A Record** | `ws` | `<YOUR_HOSTINGER_VPS_IP>` |

---

## 🛡️ Step 2: Configure Hostinger VPS Firewall

Log into Hostinger hPanel $\rightarrow$ VPS Management $\rightarrow$ **Firewall**, or set up UFW directly on your server:

```bash
# Allow SSH
sudo ufw allow 22/tcp

# Allow Web & SSL (Caddy Reverse Proxy)
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Allow LiveKit WebRTC Signaling & Media Ports
sudo ufw allow 7880/tcp
sudo ufw allow 7881/tcp
sudo ufw allow 50000:60000/udp

# Enable firewall
sudo ufw enable
```

---

## 🔑 Step 3: Deploy to Hostinger VPS

1. SSH into your Hostinger VPS:
```bash
ssh root@<YOUR_HOSTINGER_VPS_IP>
```

2. Clone repository to `/opt/42voice-livekit`:
```bash
git clone <YOUR_GIT_REPO_URL> /opt/42voice-livekit
cd /opt/42voice-livekit
```

3. Make entrypoint and deploy scripts executable:
```bash
chmod +x scripts/deploy.sh voice-agent/entrypoint.sh
```

4. Launch deployment:
```bash
./scripts/deploy.sh
```
*Or directly via Docker Compose:*
```bash
docker compose -f docker-compose.prod.yml up -d --build
```

---

## 🔍 Step 4: Verification & Default Credentials

Once deployed:
- **Frontend Dashboard**: Open `https://dashboard.42voice.com`
- **FastAPI Health Check**: `https://api.42voice.com/health` (returns `{"status":"ok"}`)
- **LiveKit Server**: `https://ws.42voice.com`

### Default Admin Credentials (Auto-seeded to Supabase)
| Role | Email | Password |
|---|---|---|
| **Super Admin** | `admin@42voice.com` | `Admin@42voice` |
| **Finance Admin** | `finance@42voice.com` | `Finance@42voice` |
| **Reseller** | `reseller@42voice.com` | `Reseller@42voice` |
| **Client** | `client@42voice.com` | `Client@42voice` |

---

## 🛠️ Logs & Management Commands

```bash
# View all container logs
docker compose -f docker-compose.prod.yml logs -f

# View LiveKit Voice Agent Worker logs
docker compose -f docker-compose.prod.yml logs -f voice-agent

# View FastAPI Backend logs
docker compose -f docker-compose.prod.yml logs -f backend

# Re-build and restart containers
docker compose -f docker-compose.prod.yml up -d --build
```
