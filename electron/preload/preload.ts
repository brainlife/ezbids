import { contextBridge, ipcRenderer } from 'electron';
console.log('run preload');
contextBridge.exposeInMainWorld('env', {
    IS_ELECTRON: process.env.IS_ELECTRON,
    API_HOST: process.env.API_HOST,
    BRAINLIFE_AUTHENTICATION: process.env.BRAINLIFE_AUTHENTICATION,
});

// links to other sites open in the app's dialog; the main process sends any it intercepts here (inAppBrowsing.ts)
contextBridge.exposeInMainWorld('ezbidsInApp', {
    onOpen: (cb: (url: string) => void) => {
        ipcRenderer.on('ezbids:open-in-app', (_event, url: string) => cb(url));
    },
});
