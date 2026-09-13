#!/bin/bash
set -e

echo "=========================================================="
echo "      42Voice - Hostinger VPS Deployment Script           "
echo "=========================================================="

# Check if .env exists
if [ ! -f .env ]; then
    echo "Error: .env file not found!"
    echo "Please copy .env.docker.example to .env and configure your Supabase & LiveKit credentials."
    exit 1
fi

# Load variables
export $(grep -v '^#' .env | xargs)

echo "[1/4] Checking Docker and Docker Compose..."
if ! command -v docker &> /dev/null; then
    echo "Docker is not installed. Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    rm get-docker.sh
fi

echo "[2/4] Stopping any existing/legacy containers..."
docker compose -f docker-compose.prod.yml down --remove-orphans 2>/dev/null || true

echo "[3/4] Pulling & Building Docker Services..."
docker compose -f docker-compose.prod.yml build --parallel

echo "[4/4] Starting 42Voice Containers..."
docker compose -f docker-compose.prod.yml up -d --remove-orphans

echo "Verifying Container Health..."
sleep 5
docker compose -f docker-compose.prod.yml ps

echo "=========================================================="
echo "  Deployment Complete!"
echo "  Frontend Dashboard: https://${DASHBOARD_DOMAIN:-dashboard.42voice.com}"
echo "  API Endpoint:       https://${API_DOMAIN:-api.42voice.com}"
echo "  LiveKit Server:     wss://${WS_DOMAIN:-ws.42voice.com}"
echo "=========================================================="
