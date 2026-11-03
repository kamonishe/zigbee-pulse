# Roadmap

## Next version: 1.0.3

- [ ] Validate timeout settings received by the dashboard WebSocket update handler before saving.
  - Enforce global mains and battery timeouts from 1 to 10080 minutes.
  - Enforce startup grace from 0 to 120 minutes.
  - Allow per-device timeout `0` only as the explicit inherit-global setting; otherwise require 1 to 10080 minutes.
  - Reject blank, non-numeric, negative, and out-of-range values without updating or reloading the integration.
  - Add coverage for valid boundaries, inheritance, blank input, and invalid ranges.
