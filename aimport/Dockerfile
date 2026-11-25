# Engine image for aimport integration tests. Build from the repo root:
#   docker build --platform linux/amd64 -t ezbids-handler:local handler/
#   docker build --platform linux/amd64 -t brainlife/aimport:dev -f aimport/Dockerfile .
# Local only: never push.

# The standalone Neuroglancer client for the QA viewer (/viewer/ng/), built from aimport/viewer-client with the
# npm versions and integrity hashes in its package-lock.json; only the static output reaches the engine image.
# build.mjs also copies uPlot's prebuilt files to vendor/uplot/ (the ephys trace viewer, /viewer/assets/uplot/).
# --ignore-scripts: no dependency runs code at install (core-js banner, esbuild binary check, fsevents,
# msgpackr-extract native addon); the output is byte-identical to a build with scripts.
FROM node:22.23.2-bookworm-slim@sha256:48e4b67d85f87bd551df43704e24d252f56cc5f8e9718841aace50f19948f0f9 AS neuroglancer-client
WORKDIR /build
COPY aimport/viewer-client/package.json aimport/viewer-client/package-lock.json aimport/viewer-client/build.mjs aimport/viewer-client/index.html ./
RUN npm ci --ignore-scripts --no-audit --no-fund && node build.mjs /opt/neuroglancer-client

# The ezBIDS root node_modules, exactly as package-lock.json pins them: the web handler (docker-compose) runs
# handler/*.ts with ../node_modules/ts-node-dev, and aimport runs ezBIDS preprocess the same way
# (ezbids_runner.ezbids_command). --ignore-scripts: no dependency runs code at install (no electron download).
FROM node:22.23.2-bookworm-slim@sha256:48e4b67d85f87bd551df43704e24d252f56cc5f8e9718841aace50f19948f0f9 AS ezbids-node-modules
WORKDIR /build
COPY package.json package-lock.json ./
RUN npm ci --workspaces=false --ignore-scripts --no-audit --no-fund

FROM ezbids-handler:local

ARG DENO_VERSION=2.5.6
# sha256 of deno-x86_64-unknown-linux-gnu.zip for DENO_VERSION (matches the release's .sha256sum)
ARG DENO_ZIP_SHA256=fd4f6abc1b6a134fa9a4dba56519f1631f44c88e04e4e3e9a8ff5975dfa66e1a
ARG BIDS_VALIDATOR_VERSION=2.4.1
ARG UV_VERSION=0.13.9
ARG PYTHON_VERSION=3.11.18
# sha256 of the file-hash listing of src/schema at the ezBIDS pin 3537e9edbc81545614d3ee605c398361099b6977
ARG EZBIDS_SPEC_SCHEMA_DIGEST=fb78c5cced1fdb3ed4a44797732caae287c50d6c6e4ce697dca149fff7a6608c

# ezBIDS code at /app (docker-compose normally mounts the repo there): the handler, its root tsconfig and
# node_modules (preprocess.ts runs with ts-node-dev, as in the web handler)
COPY handler /app/handler
COPY tsconfig.base.json /app/tsconfig.base.json
COPY --from=ezbids-node-modules /build/node_modules /app/node_modules
COPY bids-specification /app/bids-specification
COPY ui/src/assets/schema /app/ui/src/assets/schema
# Fail the build if the host submodule is empty or not at the ezBIDS pin (3537e9ed)
RUN cd /app/bids-specification/src/schema && \
    test "$(find . -type f | LC_ALL=C sort | xargs sha256sum | sha256sum | cut -d' ' -f1)" = "${EZBIDS_SPEC_SCHEMA_DIGEST}" \
    || { echo "ERROR: /app/bids-specification is not at 3537e9ed (run: git submodule update --init bids-specification)"; exit 1; }

# aimport in its own Python 3.11 venv, so it never touches the handler's python3.8 pins.
# The venv's bin goes last on PATH: system python3 stays 3.8, `pytest` is the venv's.
ENV UV_PYTHON_INSTALL_DIR=/opt/uv-python
RUN pip3 install "uv==${UV_VERSION}" "rdflib<7"  # handler image: unpinned rdflib 7 breaks prov (pydeface, pypet2bids)
RUN uv venv --python ${PYTHON_VERSION} /opt/aimport-venv && chmod -R a+rX /opt/uv-python /opt/aimport-venv
# Dependencies exactly as locked in uv.lock (versions and hashes; --locked fails if the lock is stale),
# then aimport itself without resolving anything again.
COPY aimport/pyproject.toml aimport/README.md aimport/uv.lock /tmp/aimport/
COPY aimport/src /tmp/aimport/src
RUN cd /tmp/aimport && uv export --locked --extra dev --no-emit-project -o /tmp/aimport/requirements.txt && \
    uv pip install --python /opt/aimport-venv/bin/python --require-hashes -r /tmp/aimport/requirements.txt && \
    uv pip install --python /opt/aimport-venv/bin/python --no-deps /tmp/aimport && rm -rf /tmp/aimport
ENV PATH=$PATH:/opt/aimport-venv/bin
# Tests mount the source at /src (-v $PWD/aimport:/src); run it instead of the installed copy
ENV PYTHONPATH=/src/src
ENV AIMPORT_IN_CONTAINER=1

# The QA viewer's Neuroglancer client (aimport.viewer.neuroglancer_client_dir)
COPY --from=neuroglancer-client /opt/neuroglancer-client /opt/neuroglancer-client

# BIDS v1.11.2 schema, exported from the aimport/bids-specification submodule
COPY aimport/bids-specification/src/schema /opt/bids-spec-1.11.2/src/schema
RUN mkdir -p /opt/bids-schema && \
    /opt/aimport-venv/bin/bst export --schema /opt/bids-spec-1.11.2/src/schema --output /opt/bids-schema/schema.json

# Deno BIDS validator (schema-based), pinned; cache warmed at build so it runs offline
RUN curl -fsSL -o /tmp/deno.zip https://github.com/denoland/deno/releases/download/v${DENO_VERSION}/deno-x86_64-unknown-linux-gnu.zip && \
    echo "${DENO_ZIP_SHA256}  /tmp/deno.zip" | sha256sum -c - && \
    unzip -o /tmp/deno.zip -d /usr/local/bin && rm /tmp/deno.zip
ENV DENO_DIR=/opt/deno-cache
RUN deno cache jsr:@bids/validator@${BIDS_VALIDATOR_VERSION} && chmod -R a+rX /opt/deno-cache
# The release's bundled schema is older than BIDS 1.11.2 (it flags BIDSVersion 1.11.2 as unknown),
# so the wrapper defaults --schema to the exported 1.11.2 schema (file:// works offline).
RUN printf '%s\n' \
    '#!/bin/sh' \
    'for a in "$@"; do case "$a" in -s|--schema|--schema=*|-V|--version|-h|--help) exec deno run -ERWN jsr:@bids/validator@'"${BIDS_VALIDATOR_VERSION}"' "$@";; esac; done' \
    'exec deno run -ERWN jsr:@bids/validator@'"${BIDS_VALIDATOR_VERSION}"' --schema file:///opt/bids-schema/schema.json "$@"' \
    > /usr/local/bin/bids-validator-2 && chmod +x /usr/local/bin/bids-validator-2

WORKDIR /app
