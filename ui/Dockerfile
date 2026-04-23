# Build from repo root (see docker-compose) so `npm ci -w ui` uses the root lockfile.
# `npm ci -w ui` installs only the ui workspace dependency tree — not electron/electron-builder.
FROM node:20

WORKDIR /app

# For npm to work and run npm install with specific workspaces
COPY package.json package-lock.json ./
COPY ui/package.json ./ui/
COPY electron/package.json ./electron/

RUN npm install -g npm@9.5.1 \
    && npm ci -w ui \
    && test ! -e node_modules/electron \
    && test ! -e node_modules/electron-builder

COPY ui ./ui

WORKDIR /app/ui

RUN chmod +x docker-entrypoint.sh

ENTRYPOINT ["/app/ui/docker-entrypoint.sh"]
CMD ["npm", "run", "dev"]
