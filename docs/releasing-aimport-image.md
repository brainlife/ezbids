# Releasing the aimport engine image

`.github/workflows/publish-images.yml` publishes two `linux/amd64` images to the brainlife Docker Hub org:

- `docker.io/brainlife/ezbids-handler:<version>` (from `handler/`)
- `docker.io/brainlife/aimport:<version>` (from `aimport/Dockerfile`, built on the handler image above)

## Once: add the secrets (a repo admin)

1. Before the first release, settle the FSL and ROBEX redistribution points in [CREDITS.md](../CREDITS.md#licence-notes):
   the images ship both.
2. On Docker Hub, as a member of the `brainlife` org with write access to its repositories: Account settings →
   Personal access tokens → Generate, access **Read & Write**. (Or an org access token with write to
   `brainlife/ezbids-handler` and `brainlife/aimport`; create the two repositories first if the token cannot.)
3. On GitHub, brainlife/ezbids → Settings → Secrets and variables → Actions → New repository secret:
   `DOCKERHUB_USERNAME` (the Docker Hub user, or the org name for an org token) and `DOCKERHUB_TOKEN` (the token).

Without them the workflow stops at "Check Docker Hub secrets" with an error naming both.

## Release

From an up-to-date `master` with CI green:

```
git tag aimport-v1.0.0 && git push origin aimport-v1.0.0
```

This pushes `1.0.0` and moves `latest` on both images. To publish a version without moving `latest` (a release
candidate, a rebuild), run "Publish images" from the Actions tab (or `gh workflow run publish-images.yml --ref master -f tag=1.0.0-rc.1`).

## Verify

- The run is green: it pulls both images back and runs `handler/test/image_smoke.sh`, `aimport --help` and
  `bids-validator-2 --version`.
- `docker manifest inspect docker.io/brainlife/aimport:1.0.0` and
  `docker buildx imagetools inspect docker.io/brainlife/aimport:1.0.0 --format '{{ json .Provenance }}'` (SBOM:
  `.SBOM`).
- `docker run --rm --platform linux/amd64 docker.io/brainlife/aimport:1.0.0 /opt/aimport-venv/bin/python -m aimport --help`.
