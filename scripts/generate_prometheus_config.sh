#!/usr/bin/env bash
set -euo pipefail

source .env

export GC_PROM_URL="$(cat "$GC_PROM_URL_FILE")"
export GC_PROM_USERNAME="$(cat "$GC_PROM_USERNAME_FILE")"

envsubst \
  < monitoring/prometheus.yml.tmpl \
  > monitoring/prometheus.yml