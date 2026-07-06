# Official Doc Extraction

## Lifecycle

- Red Hat publishes the RHOAI Self-Managed lifecycle so customers and partners
  can plan, deploy, and support platform infrastructure and applications.
- RHOAI Self-Managed is an Operator on Red Hat OpenShift and has a release
  schedule independent from other Red Hat products.
- Customers are expected to upgrade to the most current supported product
  version in a timely fashion.
- During Full Support, Red Hat targets security advisories, selected bug fixes,
  and qualified patches.
- Maintenance Support narrows the expected fix scope.
- Extended Update Support maintains component-specific support for supported
  components in the release.

## Release Types

- Early Access releases are unsupported, last for a short test window, and are
  intended for testing upcoming features.
- GA releases include Full Support for the lifecycle period stated by Red Hat.
- EUS releases provide a longer planning window for enterprises that prioritize
  stability.
- Red Hat recommends staying on a supported channel and the latest available
  version in that selected channel to receive support.

## Feature Maturity

- RHOAI 3.4 release notes describe new features, enhancements, resolved issues,
  known issues, support removals, and product features.
- Technology Preview features are not supported with Red Hat production SLAs,
  might not be functionally complete, and are not recommended for production.
- Developer Preview features are not supported by Red Hat in any way, are not
  production-ready, can change or be removed at any time, and may have limited
  documentation.
- Deprecated and removed items in release notes must be treated as design
  constraints for the demo.

## Demo Labeling

Use clear labels:

- `GA`: generally available according to release notes or supported
  configurations.
- `Technology Preview`: demo-only or evaluation posture; not production SLA.
- `Developer Preview`: unsupported experimental posture.
- `Deprecated`: avoid new demo dependencies unless explicitly required.
- `Removed`: do not use in active demo implementation.
- `Known issue`: document risk and workaround or avoid the affected path.
