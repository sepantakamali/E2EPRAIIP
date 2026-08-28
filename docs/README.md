# Documentation Guide

The main [`README.md`](../README.md) is the project overview and entry point.
This directory contains the detailed engineering documentation.

## Topics

- [Architecture](architecture.md): components, trust boundaries, and request flow
- [Model and dataset](model-and-dataset.md): reference task, scope, and limitations
- [Model lifecycle](model-lifecycle.md): artifacts, metadata, registry events, and pointers
- [API and security](api-and-security.md): routes, tokens, UI, and generated SDK
- [Deployment and operations](deployment-and-operations.md): local, container, and OCI operation
- [Observability](observability.md): metrics, dashboards, and alerts
- [Testing and CI/CD](testing-and-ci.md): quality gates and delivery workflows

## Terminology

- **Artifact:** an immutable joblib file containing the fitted pipeline and build metadata.
- **Registry:** the append-only `artifacts/runs.model` event log describing mutable release state.
- **Pointer:** a `latest` or `stable` reference stored in `artifacts/pointers.json`.
- **Promotion:** updating `stable` to select an already-created artifact.
- **Publication:** making an artifact available to API consumers without rewriting it.
- **Reconciliation:** combining immutable artifact metadata with later valid registry events.

Screenshots under `images/` are sanitized public documentation assets. They do
not contain credentials, public IP addresses, machine identifiers, or private
Grafana datasource identifiers.

