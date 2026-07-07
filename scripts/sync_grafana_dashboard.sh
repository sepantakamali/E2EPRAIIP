#!/usr/bin/env bash
set -euo pipefail

: "${GRAFANA_URL:?GRAFANA_URL is required}"
: "${GRAFANA_TOKEN:?GRAFANA_TOKEN is required}"

DASHBOARD_FILE="${1:-grafana/dashboards/e2epraiip-overview.json}"

jq '{
  dashboard: .,
  overwrite: true,
  folderUid: null
}' "$DASHBOARD_FILE" | curl -sS \
  -X POST \
  -H "Authorization: Bearer ${GRAFANA_TOKEN}" \
  -H "Content-Type: application/json" \
  "${GRAFANA_URL}/api/dashboards/db" \
  -d @-