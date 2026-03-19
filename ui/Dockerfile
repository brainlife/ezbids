FROM node:20

COPY . /ui
WORKDIR /ui

RUN npm install -g npm@9.5.1

RUN chmod +x /ui/docker-entrypoint.sh

ENTRYPOINT ["/ui/docker-entrypoint.sh"]
CMD [ "npm", "run", "dev" ]
