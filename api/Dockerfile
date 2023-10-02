FROM node:16

ARG USER=docker
ARG UID
ARG GID

RUN groupadd -g "${GID}" ${USER} || true
RUN useradd --create-home --no-log-init -u "${UID}" -g "${GID}" ${USER} || true

COPY . /app
RUN chown -R ${UID}:${GID} /app
WORKDIR /app/api
RUN npm install

USER ${UID}:${GID}

CMD [ "npm", "run", "dev" ]
