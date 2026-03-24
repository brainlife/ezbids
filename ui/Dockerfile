FROM node:20

WORKDIR /ui

COPY package.json package-lock.json ./
RUN npm install

COPY . .

RUN chmod +x /ui/docker-entrypoint.sh

ENTRYPOINT ["/ui/docker-entrypoint.sh"]
CMD [ "npm", "run", "dev" ]
