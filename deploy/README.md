# Deployment

This directory contains the Docker Compose files used to deploy the application on the Oracle Cloud VM.

## VM Layout

```text
/home/deploy/
├── textclf/
│   ├── .env
│   ├── artifacts/
│   ├── logs/
│   ├── deploy/
│   ├── monitoring/
│   └── nginx/
└── textclf_secrets/
```

## Prerequisites

- Docker Engine
- Docker Compose plugin
- Access to GitHub Container Registry (GHCR)
- `.env` located at `/home/deploy/textclf/.env`
- Secret files located at `/home/deploy/textclf_secrets/`

## Deploy Product

```bash
cd /home/deploy/textclf

IMAGE_TAG=<commit-sha> docker compose \
  --env-file .env \
  -f deploy/docker-compose.product.yml \
  up -d
```

## Monitoring

The monitoring stack uses the existing `textclf_observability` Docker network.
The generator uses `envsubst`, provided by `gettext-base` on Ubuntu:

```bash
sudo apt-get install gettext-base
```

In `/home/deploy/textclf/.env`, set `GC_PROM_URL_FILE` to a file containing the
Grafana Cloud HTTPS remote-write endpoint and `GC_PROM_USERNAME_FILE` to a file
containing the metrics tenant ID. Set `PROMETHEUS_METRICS_PASSWORD_FILE` and `GC_PROM_PASSWORD_FILE`
to the separate scrape and remote-write password files used by Compose.

From `/home/deploy/textclf`:

```bash
bash scripts/generate_prometheus_config.sh
docker compose --env-file .env -f deploy/docker-compose.monitor.yml pull
docker compose --env-file .env -f deploy/docker-compose.monitor.yml run --rm --no-deps --entrypoint promtool prometheus check config /etc/prometheus/prometheus.yml
docker compose --env-file .env -f deploy/docker-compose.monitor.yml up -d --force-recreate
```

The GitHub Actions monitoring workflow runs the same sequence. It generates the
configuration from the template, validates it with `promtool`, and recreates the
container to load the new file. The generated `monitoring/prometheus.yml` stays
on the deployment host and is not committed.

After deployment, check `http://127.0.0.1:9090/-/ready` on the VM and confirm the
`textclf-api` target is up in the Prometheus interface.
