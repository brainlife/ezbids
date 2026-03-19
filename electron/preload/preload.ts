import { contextBridge } from 'electron';

contextBridge.exposeInMainWorld('env', {
    IS_ELECTRON: process.env.IS_ELECTRON,
    API_HOST: process.env.API_HOST,
    BRAINLIFE_AUTHENTICATION: process.env.BRAINLIFE_AUTHENTICATION,
});
