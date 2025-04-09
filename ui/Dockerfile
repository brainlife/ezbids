FROM node:20

COPY . /ui
WORKDIR /ui

RUN npm install -g npm@9.5.1

RUN npm install

CMD [ "npm", "run", "dev" ]
