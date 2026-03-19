import { app, BrowserWindow, protocol } from 'electron';
import path from 'path';
import fs from 'fs';
import net from 'net';
import crypto from 'crypto';
import { spawn, ChildProcess } from 'child_process';

const ENVIRONMENT = process.env.NODE_ENV || 'development';
const USER_DATA_PATH = app.getPath('userData');
const APP_DIR = app.getAppPath();
const WORKDIR = path.join(USER_DATA_PATH, 'workdir');
const PROJECT_DIR = path.resolve(APP_DIR, '..');
const UPLOAD_DIR = path.join(USER_DATA_PATH, 'upload');
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

const getBinDir = (): string =>
    app.isPackaged ? path.join(process.resourcesPath, 'bin') : path.join(PROJECT_DIR, 'handler', 'bin');

const getEzBidsPlatform = (): string =>
    process.env.EZBIDS_PLATFORM ?? (process.platform === 'win32' ? 'windows' : process.platform);

const getEzBidsArch = (): string => process.env.EZBIDS_ARCH ?? (process.arch === 'arm64' ? 'arm64' : 'amd64');

console.log('ENVIRONMENT', ENVIRONMENT);

/** Backend runs from this dir (backend reads ezbids.key/ezbids.pub from its __dirname). */
const getBackendKeysDir = (): string => (ENVIRONMENT === 'development' ? path.join(APP_DIR, 'dist') : APP_DIR);

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

const startBackend = async (port: number, env: Record<string, string>): Promise<void> => {
    fs.mkdirSync(WORKDIR, { recursive: true });
    // ensureEzbidsKeys();

    if (ENVIRONMENT === 'development') {
        const backendPath = path.join(PROJECT_DIR, 'api', 'ezbids.js');
        backendProcess = spawn('node', [backendPath], {
            stdio: 'inherit' as const,
            env,
            detached: process.platform !== 'win32',
        });
        backendProcess.on('error', (err) => console.error('Backend failed to start:', err));
    } else {
        const backendPath = path.join(APP_DIR, 'dist', 'backend.cjs');
        backendProcess = spawn('node', [backendPath], {
            stdio: 'inherit' as const,
            env,
            detached: process.platform !== 'win32',
        });
        backendProcess.on('spawn', () => console.log('Backend spawned on port', port));
        backendProcess.on('error', (err) => console.error('Backend failed to start:', err));
    }
};

const startHandler = async (env: Record<string, string>): Promise<void> => {
    if (ENVIRONMENT === 'development') {
        const handlerPath = path.join(PROJECT_DIR, 'handler', 'handler.js');
        handlerProcess = spawn('node', [handlerPath], {
            stdio: 'inherit' as const,
            env,
            detached: process.platform !== 'win32',
        });
        handlerProcess.on('error', (err) => console.error('Handler failed to start:', err));
    } else {
        const handlerPath = path.join(APP_DIR, 'dist', 'handler.cjs');
        handlerProcess = spawn('node', [handlerPath], {
            stdio: 'inherit' as const,
            env,
            detached: process.platform !== 'win32',
        });
        handlerProcess.on('spawn', () => console.log('Handler spawned'));
        handlerProcess.on('error', (err) => console.error('Handler failed to start:', err));
    }
};

const startFrontend = (): Promise<void> => {
    const preloadPath = path.join(APP_DIR, 'preload', 'preload.js');
    const win = new BrowserWindow({
        width: 1000,
        height: 700,
        webPreferences: {
            preload: preloadPath,
            contextIsolation: true,
        },
    });

    // if (ENVIRONMENT === 'development') {
    win.webContents.openDevTools();
    // }

    return win.loadFile(path.join(APP_DIR, 'dist', 'frontend', 'index.html'), {});
};

async function startApp(): Promise<void> {
    const port = await getRandomPort();

    const rendererEnv = {
        BRAINLIFE_AUTHENTICATION: process.env.BRAINLIFE_AUTHENTICATION || 'false',
        IS_ELECTRON: 'true',
        API_HOST: `http://localhost:${port}`,
    };

    Object.assign(process.env, rendererEnv);

    const env = {
        ...process.env,
        USER_DATA_PATH: USER_DATA_PATH,
        UPLOAD_DIR: UPLOAD_DIR,
        PROJECT_DIR: PROJECT_DIR,
        WORKDIR: WORKDIR,
        PORT: String(port),
        MONGO_CONNECTION_STRING: '',
        EZBIDS_BIN_DIR: getBinDir(),
        EZBIDS_PLATFORM: getEzBidsPlatform(),
        EZBIDS_ARCH: getEzBidsArch(),
        ...rendererEnv,
    };
    await startBackend(port, env);
    await startHandler(env);
    await startFrontend();
}

app.whenReady().then(async () => {
    await startApp();
});

function killProcess(child: ChildProcess, name: string): void {
    if (!child.pid) {
        console.log(`${name} has no pid, skipping`);
        return;
    }
    const pid = child.pid;
    console.log(`killing ${name} (pid ${pid})`);
    try {
        if (process.platform !== 'win32') {
            console.log(`sending SIGTERM to ${name} pid ${pid}`);
            process.kill(pid, 'SIGTERM'); // to the process itself
            console.log(`sending SIGTERM to ${name} group -${pid}`);
            process.kill(-pid, 'SIGTERM'); // to the whole process group
        }
    } catch (err) {
        console.log(`error killing ${name}:`, (err as NodeJS.ErrnoException).code, err);
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

app.on('before-quit', (event) => {
    if (handlerProcess || backendProcess) {
        event.preventDefault();
        killAll();
        app.quit();
    }
});

app.on('will-quit', () => {
    console.log('will-quit event received');
    killAll();
    app.quit();
});

// When Ctrl+C is pressed in the terminal, SIGINT goes to the foreground process
// group (Electron + npm), but NOT to the handler/backend which are in their own
// process groups (detached: true). Explicitly forward these signals so the child
// process groups are killed before Electron exits.
process.on('SIGINT', () => {
    console.log('SIGINT received, killing all processes');
    app.quit();
    // killAll();
});
process.on('SIGTERM', () => {
    console.log('SIGTERM received, killing all processes');
    killAll();
    app.quit();
});

// Safety net: fires even on crashes or force-quits that bypass Electron events
process.on('exit', killAll);
process.on('uncaughtException', (err) => {
    console.error('Uncaught exception:', err);
    killAll();
    process.exit(1);
});

app.on('activate', async () => {
    if (BrowserWindow.getAllWindows().length === 0) {
        await startApp();
    }
});
