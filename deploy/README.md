# Deployment

This directory contains the Docker Compose files used to deploy the application on the Oracle Cloud VM.

## VM Layout

/home/deploy/
├── textclf/
│   ├── .env
│   ├── artifacts/
│   ├── logs/
│   ├── deploy/
│   ├── monitoring/
│   └── nginx/
└── textclf_secrets/

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