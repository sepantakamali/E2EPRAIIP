#!/usr/bin/env bash
set -euo pipefail

source .env

GC_PROM_URL="$(cat "$GC_PROM_URL_FILE")"
GC_PROM_USERNAME="$(cat "$GC_PROM_USERNAME_FILE")"
export GC_PROM_URL GC_PROM_USERNAME

envsubst '${GC_PROM_URL} ${GC_PROM_USERNAME}' \
  < monitoring/prometheus.yml.tmpl \
  > monitoring/prometheus.yml
