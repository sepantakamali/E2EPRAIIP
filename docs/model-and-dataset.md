# Model and Dataset

## Reference task

The repository serves a deliberately small binary text-classification model.
Training data comes from a selected subset of scikit-learn's
`fetch_20newsgroups` dataset, with application-facing labels configured by the
UI.

This model provides a concrete workload for practising the complete inference
lifecycle. It is not presented as a novel dataset, architecture, benchmark, or
research result.

## Why a simple model is useful here

A lightweight classifier keeps training and verification inexpensive while the
project concentrates on production concerns:

- deterministic data loading and train/test splitting
- a fitted text-processing and classification pipeline
- serialised artifacts with immutable identity
- API request and response contracts
- publication and promotion
- container deployment and runtime health
- authentication, monitoring, alerting, and recovery

## Boundaries

- The API schema and UI are designed for this binary classification task.
- The model is not evidence of high-scale or distributed inference.
- Dataset content retains its original provenance and is not authored by this project.
- The reusable output is the engineering approach, not a claim that the service
  already hosts arbitrary AI workloads.

See scikit-learn's dataset documentation for the source dataset's description
and provenance: <https://scikit-learn.org/stable/modules/generated/sklearn.datasets.fetch_20newsgroups.html>.

