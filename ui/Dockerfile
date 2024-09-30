FROM node:20

COPY . /ui
WORKDIR /ui

RUN npm install

CMD [ "npm", "run","${UI_PACKAGE_JSON_SCRIPT}" ]
