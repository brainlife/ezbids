import { app, BrowserWindow, ipcMain, protocol } from 'electron';
import path from 'path';
import fs from 'fs';
import net from 'net';
import crypto from 'crypto';
import { fileURLToPath } from 'url';
import { spawn, ChildProcess } from 'child_process';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = path.join(__dirname, '..');
const WORKDIR = path.join(PROJECT_ROOT, 'tmp', 'ezbids-workdir');

const ENVIRONMENT = process.env.NODE_ENV || 'development';
const RENDERER_DIST_PATH = path.join(__dirname, '../ui/dist');

protocol.registerSchemesAsPrivileged([{ scheme: 'app', privileges: { standard: true } }]);

let backendProcess: ChildProcess | null = null;
let apiPort: number = 0;

/** Returns a random unused port (for deploy-friendly binding). */
const getRandomPort = (): Promise<number> =>
    new Promise((resolve, reject) => {
        const server = net.createServer();
        server.listen(0, () => {
            const addr = server.address();
            const port = addr && typeof addr === 'object' ? addr.port : 0;
            server.close(() => (port ? resolve(port) : reject(new Error('could not get port'))));
        });
        server.on('error', reject);
    });

/** Backend runs from this dir (backend reads ezbids.key/ezbids.pub from its __dirname). */
const getBackendKeysDir = (): string =>
    ENVIRONMENT === 'development' ? path.join(__dirname, 'dist') : __dirname;

/** Ensure ezbids.pub and ezbids.key exist for JWT; auto-generate fake keys for testing if missing. */
const ensureEzbidsKeys = (): void => {
    const keysDir = getBackendKeysDir();
    const keyPath = path.join(keysDir, 'ezbids.key');
    const pubPath = path.join(keysDir, 'ezbids.pub');
    if (fs.existsSync(keyPath) && fs.existsSync(pubPath)) return;

    fs.mkdirSync(keysDir, { recursive: true });
    const { privateKey, publicKey } = crypto.generateKeyPairSync('rsa', {
        modulusLength: 2048,
        publicKeyEncoding: { type: 'spki', format: 'pem' },
        privateKeyEncoding: { type: 'pkcs1', format: 'pem' },
    });
    fs.writeFileSync(keyPath, privateKey, 'ascii');
    fs.writeFileSync(pubPath, publicKey, 'ascii');
};

const startBackend = async (): Promise<void> => {
    fs.mkdirSync(WORKDIR, { recursive: true });
    ensureEzbidsKeys();

    const port = process.env.PORT ? parseInt(process.env.PORT, 10) : await getRandomPort();
    apiPort = port;

    const env = {
        ...process.env,
        WORKDIR: WORKDIR,
        PORT: String(port),
        MONGO_CONNECTION_STRING: process.env.MONGO_CONNECTION_STRING || 'mongodb://localhost:27017/ezbids',
    };

    if (ENVIRONMENT === 'development') {
        const backendPath = path.join(__dirname, 'dist', 'backend.cjs');
        backendProcess = spawn('node', [backendPath], { stdio: 'inherit', env });
        backendProcess.on('spawn', () => console.log('Backend spawned on port', port));
        backendProcess.on('error', (err) => console.error('Backend failed to start:', err));
    } else {
        const backendPath = path.join(__dirname, 'backend.js');
        backendProcess = spawn('node', [backendPath], { stdio: 'inherit', env });
        backendProcess.on('error', (err) => console.error('Backend failed to start:', err));
    }
};

const startFrontend = (): Promise<void> => {
    const preloadPath = path.join(__dirname, 'preload', 'preload.js');
    const win = new BrowserWindow({
        width: 1000,
        height: 700,
        webPreferences: {
            preload: preloadPath,
            contextIsolation: true,
        },
    });

    if (ENVIRONMENT === 'development') {
        win.webContents.openDevTools();
        return win.loadURL('http://localhost:3000');
    } else {
        return win.loadFile(path.join(__dirname, '../ui/dist', 'index.html'));
    }
};

const createWindow = async (): Promise<void> => {
    await startBackend();
    await startFrontend();
};

app.whenReady().then(() => {
    ipcMain.handle('getApiUrl', () => `http://localhost:${apiPort}`);
    ipcMain.handle('pingPython', (_event, _args: unknown) => {
        const pythonProcess = spawn('python3', ['hello.py']);
        pythonProcess.stdout.on('data', (data: Buffer | string) => {
            console.log(`stdout: ${data}`);
        });
        pythonProcess.stderr.on('data', (data: Buffer | string) => {
            console.error(`stderr: ${data}`);
        });
        pythonProcess.on('close', (code: number | null) => {
            console.log(`child process exited with code ${code}`);
        });
    });
    createWindow();
});

app.on('window-all-closed', () => {
    if (backendProcess) {
        console.log('killing backend process');
        backendProcess.kill();
        backendProcess = null;
    }
    if (process.platform !== 'darwin') app.quit();
});

app.on('before-quit', () => {
    if (backendProcess) {
        console.log('killing backend process');
        backendProcess.kill();
        backendProcess = null;
    }
});

app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
});
