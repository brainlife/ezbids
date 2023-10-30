require('dotenv').config({ path:'../.env' })

import express from 'express';
import bodyParser from 'body-parser';
import compression from  'compression';
import cors from 'cors';
import nocache from 'nocache';

import { models } from 'ezbids-shared';

import controllers from "./controllers";

// setup swagger
import swaggerUi = require('swagger-ui-express');
import swaggerJsdoc = require('swagger-jsdoc');

const options = {
    definition: {
      openapi: '3.0.0',
      info: {
        title: 'EZBIDS API',
        version: '1.0.0',
      },
    },
    apis: ['./controllers.js'], // files containing annotations as above
  };
const swaggerSpec = swaggerJsdoc(options);

//init express
const app: express.Application  = express();
app.use(cors({ origin: '*' }));
app.use(compression());
app.use(nocache());

app.disable('x-powered-by');

app.use(bodyParser.urlencoded({
    limit: '50gb',
    extended: true
  }));

app.use(bodyParser.json({
    limit: '50mb',
    type: "application/json",
}));

app.use('/', controllers);

app.use('/api/docs', swaggerUi.serve, swaggerUi.setup(swaggerSpec));
//error handling
//app.use(expressWinston.errorLogger(config.logger.winston)); 
app.use(function(err, req, res, next) {
    if (typeof err === "string") err = { message: err };
    if (!err.name || err.name != "UnauthorizedError") {
        console.error(err);
    }
    if (err.stack) err.stack = "hidden"; //don't sent call stack to UI - for security reason
    res.status(err.status || 500);
    res.json(err);
});

process.on('uncaughtException', err=>{
    console.error((new Date).toUTCString() + ' uncaughtException:', err.message)
    console.error(err.stack)
});

models.connect(err=>{
  if (err) throw err;
  const port = +(process.env.PORT || '8082');
  const host = process.env.HOST || 'localhost';
  app.listen(port, host, function() {
    console.log("ezbids api service running on %s:%d in %s mode", host, port, app.settings.env);
  });
});
