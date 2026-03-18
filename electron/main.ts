import { app, BrowserWindow, ipcMain, protocol } from 'electron';
import path from 'path';
import fs from 'fs';
import net from 'net';
import crypto from 'crypto';
import { fileURLToPath } from 'url';
import { spawn, ChildProcess } from 'child_process';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const USER_DATA_PATH = app.getPath('userData');
const WORKDIR = path.join(USER_DATA_PATH, 'workdir');

const ENVIRONMENT = process.env.NODE_ENV || 'development';
const RENDERER_DIST_PATH = path.join(__dirname, '../ui/dist');

protocol.registerSchemesAsPrivileged([{ scheme: 'app', privileges: { standard: true } }]);

let backendProcess: ChildProcess | null = null;
let handlerProcess: ChildProcess | null = null;

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

const port = process.env.PORT ? parseInt(process.env.PORT, 10) : await getRandomPort();

/** Dir containing packaged binaries (7z, etc.). Handler/expand uses EZBIDS_BIN_DIR to find them. */
const getBinDir = (): string =>
    app.isPackaged ? path.join(process.resourcesPath, 'bin') : path.join(__dirname, '../handler/bin');

/** Platform for binary naming: darwin | linux | windows (matches fetch-binaries / getDcm2niixExecutable). */
const getEzBidsPlatform = (): string =>
    process.env.EZBIDS_PLATFORM ?? (process.platform === 'win32' ? 'windows' : process.platform);

/** Arch for binary naming: amd64 | arm64. */
const getEzBidsArch = (): string => process.env.EZBIDS_ARCH ?? (process.arch === 'arm64' ? 'arm64' : 'amd64');

const env = {
    ...process.env,
    USER_DATA_PATH: USER_DATA_PATH,
    UPLOAD_DIR: path.join(USER_DATA_PATH, 'upload'),
    PROJECT_DIR: path.join(__dirname, '..'),
    WORKDIR: WORKDIR,
    PORT: String(port),
    BRAINLIFE_AUTHENTICATION: process.env.BRAINLIFE_AUTHENTICATION || 'false',
    IS_ELECTRON: 'true',
    MONGO_CONNECTION_STRING: '',
    EZBIDS_BIN_DIR: getBinDir(),
    EZBIDS_PLATFORM: getEzBidsPlatform(),
    EZBIDS_ARCH: getEzBidsArch(),
};

/** Backend runs from this dir (backend reads ezbids.key/ezbids.pub from its __dirname). */
const getBackendKeysDir = (): string => (ENVIRONMENT === 'development' ? path.join(__dirname, 'dist') : __dirname);

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

/**
 * On POSIX, spawn with detached:true so the child becomes a process group
 * leader. This lets killProcess target the entire group (all grandchildren too)
 * via process.kill(-pid, 'SIGKILL'). On Windows detached would open a new
 * console, so we leave it false there (taskkill /T handles the tree instead).
 */
const spawnOpts = { stdio: 'inherit' as const, env, detached: process.platform !== 'win32' };

const startBackend = async (): Promise<void> => {
    fs.mkdirSync(WORKDIR, { recursive: true });
    ensureEzbidsKeys();

    if (ENVIRONMENT === 'development') {
        const backendPath = path.join(__dirname, 'dist', 'backend.cjs');
        backendProcess = spawn('node', [backendPath], spawnOpts);
        backendProcess.on('spawn', () => console.log('Backend spawned on port', port));
        backendProcess.on('error', (err) => console.error('Backend failed to start:', err));
    } else {
        const backendPath = path.join(__dirname, 'backend.js');
        backendProcess = spawn('node', [backendPath], spawnOpts);
        backendProcess.on('error', (err) => console.error('Backend failed to start:', err));
    }
};

const startHandler = async (): Promise<void> => {
    const handlerPath = path.join(__dirname, '../handler', 'handler.js');
    handlerProcess = spawn('node', [handlerPath], spawnOpts);
    handlerProcess.on('error', (err) => console.error('Handler failed to start:', err));
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
    await startHandler();
};

app.whenReady().then(() => {
    ipcMain.handle('getApiUrl', () => `http://localhost:${port}`);
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

function killProcess(child: ChildProcess, name: string): void {
    if (!child.pid) return;
    console.log(`killing ${name} (pid ${child.pid})`);
    try {
        if (process.platform === 'win32') {
            spawn('taskkill', ['/F', '/T', '/PID', String(child.pid)], { stdio: 'ignore' });
        } else {
            process.kill(-child.pid, 'SIGKILL'); // dont just kill process, but kill the entire process group
        }
    } catch (err) {
        console.error(`Failed to kill ${name}:`, err);
    }
}

function killAll(): void {
    if (backendProcess) {
        killProcess(backendProcess, 'backend');
        backendProcess = null;
    }
    if (handlerProcess) {
        killProcess(handlerProcess, 'handler');
        handlerProcess = null;
    }
}

app.on('window-all-closed', () => {
    killAll();
    if (process.platform !== 'darwin') app.quit();
});

app.on('before-quit', () => {
    killAll();
});

app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
});
