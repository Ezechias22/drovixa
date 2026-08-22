#!/usr/bin/env sh
set -eu

: "${1:?Usage: smoke-test.sh API_ORIGIN APP_ORIGIN ADMIN_ORIGIN}"
: "${2:?Usage: smoke-test.sh API_ORIGIN APP_ORIGIN ADMIN_ORIGIN}"
: "${3:?Usage: smoke-test.sh API_ORIGIN APP_ORIGIN ADMIN_ORIGIN}"

API_ORIGIN="${1%/}"
APP_ORIGIN="${2%/}"
ADMIN_ORIGIN="${3%/}"

curl --fail --silent --show-error "${API_ORIGIN}/api/v1/health/ready" >/dev/null
curl --fail --silent --show-error "${API_ORIGIN}/api/v1/genres" >/dev/null
curl --fail --silent --show-error "${APP_ORIGIN}/" >/dev/null
curl --fail --silent --show-error "${ADMIN_ORIGIN}/login" >/dev/null

echo "Drovixa smoke tests passed."
