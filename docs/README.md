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

For reproducibility limitations and remaining cleanup, see the
[repository review](repository-review.md).

## Terminology

- **Artifact:** an immutable joblib file containing the fitted pipeline and build metadata.
- **Registry:** the append-only `artifacts/runs.model` event log describing mutable release state.
- **Pointer:** a `latest` or `stable` reference stored in `artifacts/pointers.json`.
- **Promotion:** updating `stable` to select an already-created artifact.
- **Publication:** making an artifact available to API consumers without rewriting it.
- **Reconciliation:** combining immutable artifact metadata with later valid registry events.

- **Resolution:** turning a selector such as `stable` into the artifact file to load.
- **Registry overlay:** later release information stored outside the immutable model file.
- **Split invariants:** required properties of the training/test sets, such as matching text and label counts.
- **Local Prometheus rules:** rules evaluated by Prometheus on the VM, as distinct from Grafana Cloud.

Screenshots under `images/` are sanitized public documentation assets. They do
not contain credentials, public IP addresses, machine identifiers, or private
Grafana datasource identifiers.

