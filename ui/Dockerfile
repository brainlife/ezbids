FROM node:16

COPY . /ui
WORKDIR /ui

RUN npm install
RUN chown -R node:node /ui

CMD [ "npm", "run", "dev" ]
