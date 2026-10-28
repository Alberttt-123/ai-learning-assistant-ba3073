#!/usr/bin/env bash

set -uo pipefail
umask 077

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_URL="${AILA_BACKEND_URL:-http://127.0.0.1:14242}"
OUTPUT_FILE="${AILA_CHECK_OUTPUT:-${ROOT_DIR}/ecs-docker-check.txt}"
COMPOSE_FILE="${AILA_COMPOSE_FILE:-${ROOT_DIR}/compose.ecs.yml}"
ECS_PUBLIC_IP="${1:-}"
if [ -z "${ECS_PUBLIC_IP}" ]; then
  read -r -p 'ECS public IPv4 address: ' ECS_PUBLIC_IP
fi
if ! [[ "${ECS_PUBLIC_IP}" =~ ^[0-9]{1,3}(\.[0-9]{1,3}){3}$ ]]; then
  echo 'Usage: sudo bash scripts/check-ecs-docker.sh PUBLIC_IPV4' >&2
  exit 2
fi

exec > >(tee "${OUTPUT_FILE}") 2>&1

fail() {
  echo
  echo "Result: FAIL"
  echo "[FAIL] $1" >&2
  exit 1
}

echo "AI Learning Assistant ECS Docker Check"
echo "Checked at: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
date '+Time (local): %Y-%m-%dT%H:%M:%S%z'
printf 'Machine: %s\n' "$(hostname)"
printf 'Operating system: %s\n' "$(uname -sr)"
printf 'CPU architecture: %s\n' "$(uname -m)"
printf 'ECS login user: %s\n' "$(whoami)"
printf 'Website URL: http://%s:14242/ui/\n' "${ECS_PUBLIC_IP}"
echo "Output file: ${OUTPUT_FILE}"
echo
echo "Checking the AI Learning Assistant runtime on this ECS server..."

if ! command -v docker >/dev/null 2>&1; then
  fail "Docker is not installed or is not available in PATH."
fi
echo "[OK] Docker CLI is installed."
docker --version

if ! docker info >/dev/null 2>&1; then
  fail "The Docker daemon is not running, or this user does not have permission to access it."
fi
echo "[OK] Docker daemon is running."

if ! docker compose version >/dev/null 2>&1; then
  fail "The Docker Compose plugin is not available."
fi
echo "[OK] Docker Compose is available."
docker compose version
printf '\nDocker application container:\n'
docker ps -a --filter publish=14242 --format 'table {{.ID}}\t{{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}' || fail 'Cannot list containers.'

running_services="$(docker compose -p ai-learning-assistant -f "${COMPOSE_FILE}" ps --status running --services 2>/dev/null)"
if ! grep -qx "backend" <<<"${running_services}"; then
  fail "The backend container is not running for this Compose project."
fi
echo "[OK] Backend container is running."

if ! command -v curl >/dev/null 2>&1; then
  fail "curl is required to check the application health endpoint."
fi

if ! curl -fsS "${BACKEND_URL}/health" >/dev/null 2>&1; then
  fail "The backend container is running, but ${BACKEND_URL}/health did not respond successfully."
fi
echo "[OK] Application health check passed at ${BACKEND_URL}/health."

ui_status="$(curl --noproxy '*' -sS --connect-timeout 5 --max-time 15 \
  -o /dev/null -w '%{http_code}' "http://${ECS_PUBLIC_IP}:14242/ui/")"
curl_code=$?
printf 'Public-IP UI HTTP status: %s\n' "${ui_status}"
if [ "${curl_code}" -ne 0 ] || [ "${ui_status}" != 200 ]; then
  fail "Website URL check failed (curl exit code: ${curl_code})."
fi
echo 'Website URL check: PASS'

echo
echo "Result: PASS"
echo "Docker and the AI Learning Assistant are running correctly on this ECS server."
echo 'Browser rendering and access from the student computer require separate evidence.'
