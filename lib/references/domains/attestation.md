# Attestation

**CLI only. Supply chain security — verify artifact provenance.**

| Operation | gh CLI | REST | GraphQL | Web UI | Notes |
|-----------|--------|------|---------|--------|-------|
| Verify | ✓ | ✗ | ✗ | ✓ | Verify artifact attestation |
| Download | ✓ | ✗ | ✗ | ✗ | Download attestation bundle |
| Trusted root | ✓ | ✗ | ✗ | ✗ | Manage trusted roots |

## CLI Command Reference

| Operation | Command | Notes |
|-----------|---------|-------|
| Verify | `gh attestation verify {artifact}` | Verify artifact provenance |
| Download | `gh attestation download {artifact}` | Download attestation bundle |
| Trusted root | `gh attestation trusted-root` | Manage trusted roots |

**Note:** Attestation is a CLI-only feature with no REST or GraphQL API. It verifies that artifacts were built in trusted environments using Sigstore-based attestations.
