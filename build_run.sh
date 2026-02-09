#!/usr/bin/env bash
set -euo pipefail

# Navigate to script directory
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

echo "[1/7] Loading env..."

source ./env.sh

echo "[2/7] Build order-service (no-cache)..."
docker build --no-cache -t order-service-image:latest order-service/

echo "[3/7] Build payment-service (no-cache)..."
docker build --no-cache -t payment-service-image:latest payment-service/

echo "[4/7] Build backend (no-cache)..."
docker build --no-cache -t backend-image:latest backend/

echo "[5/7] Build frontend (no-cache + build args)..."
docker build --no-cache -t frontend-image:latest \
  --build-arg VITE_BACKEND_URL=/api \
  --build-arg VITE_KEYCLOAK_URL=http://127.0.0.1:8081 \
  frontend/

echo "[6/7] Deploy stack..."
docker stack deploy -c stack.yml alpstore

echo "[7/7] Waiting 15s for services to initialize..."
sleep 15

echo "Done."
echo "Traefik:   http://127.0.0.1:8088"
echo "Frontend:  http://127.0.0.1/"
echo "Backend:   http://127.0.0.1/api/"
echo "Keycloak:  http://127.0.0.1:8081"
