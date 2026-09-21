# Repository presentation review

Reviewed 21 September 2026 against the local checkout. This is a source and
configuration review, not a live VM audit or a Git-history secret audit.

The overview, focused documentation, screenshots, and separation of model and
application releases make this a presentable production-engineering reference
project. Its contribution is the surrounding engineering, not model novelty.
The following remaining limitations matter when demonstrating reproducibility
and interpreting operational claims.

## Quick fixes completed

- Prediction calls entering the handler now increment the request counter once,
  whether they succeed or fail. Failures increment the error counter once.
  Regression tests cover successful calls, missing artifacts, failed loading,
  input limits, unexpected failures, and pre-handler rejections. Authentication
  and schema failures before handler entry are deliberately excluded.
- The Prometheus template and tracked configuration now both scrape and evaluate
  rules every 15 seconds. The deployment workflow uses the tracked configuration.
- Package metadata now requires Python 3.11 or newer, matching the minimum needed
  by the pinned numerical dependencies. CI and the container use Python 3.11;
  this does not claim that CI covers every later version.

## Remaining design and operational limitations

1. **Monitoring configuration is still maintained in two files.**
   The tracked YAML contains deployment-specific endpoint and tenant settings;
   the template uses placeholders. Its `.gitignore` entry does not untrack the
   existing YAML. Future configuration changes should update both, or move to a
   single rendering workflow. Passwords remain in mounted secret files.
2. **Metrics isolation trusts internal workloads.**
   The proxy checks Basic credentials, but direct API `/metrics` access checks
   internal IP ranges. Internal HTTP is unencrypted. This is an internal-network
   trust model, not exclusive authentication of one Prometheus instance.
3. **Infrastructure recreation is partly manual.**
   Docker networks, certificates, host backup helpers/systemd units, and Grafana
   contact points/routing are not fully provisioned by the repository. The
   production deployment guide must be treated as a description of an existing
   installation, not a complete fresh-VM bootstrap procedure.

## Optional presentation improvements

- Add a license only after the owner chooses the intended reuse terms.
- Move or remove unused logo bundles and clearly label `the_messy_baseline.py`
  as historical material; they distract from the main repository structure.
- Consider archiving old demonstration model artifacts outside the primary
  repository once retention requirements are decided.
- Hide the internal API address in an end-user UI if operator diagnostics are
  not part of the intended demonstration. The address does not publish the port.

The existing `requests.Session` UI is a reasonable choice. Retain the SDK as an
explicitly optional integration example rather than introducing an additional
abstraction solely to use generated code.
