FROM node:20

COPY . /app

WORKDIR /app

RUN npm install -g npm@9.5.1

RUN npm install -g pm2 typescript tsc-watch

RUN npm install
