FROM node:16

COPY . /app

WORKDIR /app
RUN npm install -g pm2 typescript

RUN npm install

