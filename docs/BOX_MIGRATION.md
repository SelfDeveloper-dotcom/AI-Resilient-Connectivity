# Box Migration Plan

The local directory is the active SRC for development. When Box is ready:

1. Create a Box application/service account with least-privilege access.
2. Create operator-specific folders or map existing folder IDs.
3. Install `requirements-box.txt`.
4. Store credentials outside Git (`.env`, secret store or OS environment).
5. Implement/enable the Box adapter to download only new file versions into the same immutable raw archive.
6. Preserve Box file ID, version ID and modified timestamp in the submission registry.
7. Keep Collector -> PP -> Feature Engineering -> Model unchanged.

Do not place Box credentials in source code or GitHub.
