FROM node:20

WORKDIR /app

RUN npm install -g npm@9.5.1

RUN npm install -g pm2 typescript tsc-watch

# For npm to work and run npm install with specific workspaces
COPY package.json package-lock.json ./
COPY ui/package.json ./ui/
COPY electron/package.json ./electron/

# API/runtime only: root deps from the lockfile — not ui or electron workspace packages (avoids
# pulling Vite, electron, electron-builder, etc. into this image).
RUN npm ci --workspaces=false

COPY tsconfig.base.json ./
COPY api ./api
