import { contextBridge, ipcRenderer } from 'electron';
console.log('run preload');
contextBridge.exposeInMainWorld('env', {
    IS_ELECTRON: process.env.IS_ELECTRON,
    API_HOST: process.env.API_HOST,
    BRAINLIFE_AUTHENTICATION: process.env.BRAINLIFE_AUTHENTICATION,
});

// AI import (aimport engine). The engine's token stays in the main process; calls go through it.
contextBridge.exposeInMainWorld('aimport', {
    pickFolder: (): Promise<string | null> => ipcRenderer.invoke('aimport:pick-folder'),
    start: (inputDir: string): Promise<{ ok: boolean; inputDir?: string; error?: string }> =>
        ipcRenderer.invoke('aimport:start', inputDir),
    api: (method: 'GET' | 'POST' | 'PATCH', path: string, body?: unknown): Promise<{ status: number; data: any }> =>
        ipcRenderer.invoke('aimport:api', method, path, body),
    openViewer: (): Promise<{ ok: boolean; error?: string }> => ipcRenderer.invoke('aimport:open-viewer'),
    showOutput: (): Promise<{ ok: boolean }> => ipcRenderer.invoke('aimport:show-output'),
    stop: (): Promise<void> => ipcRenderer.invoke('aimport:stop'),
});
