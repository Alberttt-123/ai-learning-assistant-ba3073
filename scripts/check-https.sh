#!/usr/bin/env bash
# Usage: bash scripts/check-https.sh ai.example.com /path/to/private.netrc
# Credentials stay in an owner-only netrc file, never CLI arguments.
set -euo pipefail
umask 077
domain="${1:?Provide the real domain without scheme or path}"
netrc="${2:?Provide an existing private netrc file with proxy credentials}"
[[ "$domain" =~ ^[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?$ ]] || exit 2
[[ -f "$netrc" ]] || exit 2
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec > >(tee "${AILA_HTTPS_REPORT:-${ROOT_DIR}/https-access-check.txt}") 2>&1
date -u '+Time (UTC): %Y-%m-%dT%H:%M:%SZ'
echo "HTTPS URL: https://${domain}/ui/"
# No -k: certificate and hostname validation must pass.
redirect="$(curl --noproxy '*' -sS --max-time 20 -o /dev/null -w '%{redirect_url}' "http://${domain}/ui/")"
[[ "$redirect" = "https://${domain}/ui/" ]] || { echo 'HTTP redirect: FAIL'; exit 1; }
echo 'HTTP redirect: PASS'
status="$(curl --noproxy '*' -sS --max-time 20 -o /dev/null -w '%{http_code}' "https://${domain}/ui/")"
[[ "$status" = 401 ]] || { echo "Proxy unauthenticated rejection: FAIL ($status)"; exit 1; }
echo 'Proxy unauthenticated rejection: PASS (401)'
page="$(curl --noproxy '*' -fsS --max-time 20 --netrc-file "$netrc" "https://${domain}/ui/")"
[[ "$page" = *'name="aila-session-header" content="X-App-Authorization"'* ]] || { echo 'UI proxy session mode: FAIL'; exit 1; }
echo 'Authenticated HTTPS UI and proxy session mode: PASS'
health="$(curl --noproxy '*' -fsS --max-time 20 --netrc-file "$netrc" "https://${domain}/health")"
[[ "$health" = *'"status":"ok"'* ]] || { echo 'Health: FAIL'; exit 1; }
echo 'Authenticated HTTPS health: PASS'
echo 'Result: PASS. Browser sign-in and real artifact generation still require verification.'
