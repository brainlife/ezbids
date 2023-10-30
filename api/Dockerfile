FROM node:16 as base

ARG USER=docker
ARG UID
ARG GID

RUN groupadd -g "${GID}" ${USER} || true
RUN useradd --create-home --no-log-init -u "${UID}" -g "${GID}" ${USER} || true

COPY . /app

WORKDIR /app/shared
RUN npm install

WORKDIR /app/api
RUN npm install

USER ${UID}:${GID}

CMD [ "npm", "run", "dev" ]

FROM base as production

RUN npm run build

CMD [ "node", "./build/api/ezbids.js" ]