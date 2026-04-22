/* eslint-disable no-console */
import { app, BrowserWindow, protocol } from 'electron';
import path from 'path';
import fs from 'fs';
import net from 'net';
import { spawn, ChildProcess } from 'child_process';
import { createRequire } from 'module';
import treeKill from 'tree-kill';
const require = createRequire(import.meta.url);

const ENVIRONMENT = app.isPackaged ? 'production' : 'development';
const USER_DATA_PATH = app.getPath('userData');
const APP_DIR = app.getAppPath(); // In production, APP_DIR looks like .../release/mac-arm64/ezBIDS.app/Contents/Resources/app
const WORKDIR = path.join(USER_DATA_PATH, 'workdir');
const LOCAL_PROJECT_DIR = path.resolve(APP_DIR, '..');
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
    ENVIRONMENT === 'production'
        ? path.join(process.resourcesPath, 'bin')
        : path.join(LOCAL_PROJECT_DIR, 'handler', 'bin');

const getProjectPath = (...relativePathSegments: string[]): string =>
    ENVIRONMENT === 'production'
        ? path.join(APP_DIR, ...relativePathSegments)
        : path.join(LOCAL_PROJECT_DIR, ...relativePathSegments);

const getEzBidsPlatform = (): string =>
    process.env.EZBIDS_PLATFORM ?? (process.platform === 'win32' ? 'windows' : process.platform);

const getEzBidsArch = (): string => process.env.EZBIDS_ARCH ?? (process.arch === 'arm64' ? 'arm64' : 'amd64');

const startBackend = async (port: number, env: Record<string, string>): Promise<void> => {
    console.log(`Starting backend in ${ENVIRONMENT} environment`);
    fs.mkdirSync(WORKDIR, { recursive: true });

    if (ENVIRONMENT === 'development') {
        const tsNodeDevBin = require.resolve('ts-node-dev/lib/bin.js');
        backendProcess = spawn(
            process.execPath,
            [
                tsNodeDevBin,
                '--transpile-only',
                '--debounce',
                '2000',
                '--watch',
                env.EZBIDS_BACKEND_DIR,
                '-P',
                path.join(env.EZBIDS_BACKEND_DIR, 'tsconfig.json'),
                path.join(env.EZBIDS_BACKEND_DIR, 'ezbids.ts'),
            ],
            {
                cwd: env.EZBIDS_BACKEND_DIR,
                stdio: 'inherit' as const,
                env,
                detached: false,
            }
        );
        backendProcess.on('error', (err) => console.error('Backend failed to start:', err));
    } else {
        backendProcess = spawn(process.execPath, [path.join(env.EZBIDS_BACKEND_DIR, 'ezbids.cjs')], {
            stdio: 'inherit' as const,
            env,
            detached: getEzBidsPlatform() !== 'windows',
        });
        backendProcess.on('spawn', () => console.log('Backend spawned on port', port));
        backendProcess.on('error', (err) => console.error('Backend failed to start:', err));
    }
};

const startHandler = async (env: Record<string, string>): Promise<void> => {
    console.log(`Starting handler in ${ENVIRONMENT} environment`);
    if (ENVIRONMENT === 'development') {
        const tsNodeDevBin = require.resolve('ts-node-dev/lib/bin.js');
        handlerProcess = spawn(
            process.execPath,
            [
                tsNodeDevBin,
                '--transpile-only',
                '--debounce',
                '2000',
                '--watch',
                env.EZBIDS_HANDLER_DIR,
                '-P',
                path.join(env.EZBIDS_HANDLER_DIR, 'tsconfig.json'),
                path.join(env.EZBIDS_HANDLER_DIR, 'handler.ts'),
            ],
            {
                cwd: env.EZBIDS_HANDLER_DIR,
                stdio: 'inherit' as const,
                env,
                detached: false,
            }
        );
        handlerProcess.on('error', (err) => console.error('Handler failed to start:', err));
    } else {
        handlerProcess = spawn(process.execPath, [path.join(env.EZBIDS_HANDLER_DIR, 'handler.cjs')], {
            stdio: 'inherit' as const,
            env,
            detached: getEzBidsPlatform() !== 'windows',
        });
        handlerProcess.on('spawn', () => console.log('Handler spawned'));
        handlerProcess.on('error', (err) => console.error('Handler failed to start:', err));
    }
};

const startFrontend = (): Promise<void> => {
    console.log(`Starting frontend in ${ENVIRONMENT} environment`);

    console.log('APP_DIR', APP_DIR);

    const preloadPath = path.join(APP_DIR, 'preload', 'preload.js');
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
    }

    return win.loadFile(path.join(APP_DIR, 'dist', 'frontend', 'index.html'), {});
};

async function startApp(): Promise<void> {
    let port = 8080;
    if (ENVIRONMENT === 'production') {
        port = await getRandomPort();
    }

    /**
     * Note: These variables are separated from the rest of the env object as they will be assigned to
     * process.env and passed to the frontend.
     */
    const rendererEnv = {
        BRAINLIFE_AUTHENTICATION: process.env.BRAINLIFE_AUTHENTICATION || 'false',
        IS_ELECTRON: 'true',
        API_HOST: `http://localhost:${port}`,
    };

    Object.assign(process.env, rendererEnv);

    const ezbidsHandlerDir =
        ENVIRONMENT === 'production' ? getProjectPath('dist', 'handler') : getProjectPath('handler');
    const bidsValidatorPath = getProjectPath('node_modules', 'bids-validator', 'bin', 'bids-validator');
    const ezbidsBackendDir = ENVIRONMENT === 'production' ? getProjectPath('dist') : getProjectPath('api');

    const env = {
        ...process.env,
        USER_DATA_PATH: USER_DATA_PATH,
        UPLOAD_DIR: UPLOAD_DIR,
        WORKDIR: WORKDIR,
        PORT: String(port),
        MONGO_CONNECTION_STRING: '',
        EZBIDS_BIN_DIR: getBinDir(),
        EZBIDS_HANDLER_DIR: ezbidsHandlerDir,
        EZBIDS_PREPROCESS_PATH: path.join(
            ezbidsHandlerDir,
            ENVIRONMENT === 'production' ? 'preprocess.cjs' : 'preprocess.ts'
        ),
        EZBIDS_EXPAND_PATH: path.join(ezbidsHandlerDir, ENVIRONMENT === 'production' ? 'expand.cjs' : 'expand.ts'),
        EZBIDS_BIDS_PATH: path.join(ezbidsHandlerDir, ENVIRONMENT === 'production' ? 'bids.cjs' : 'bids.ts'),
        EZBIDS_CONVERT_PATH: path.join(ezbidsHandlerDir, ENVIRONMENT === 'production' ? 'convert.cjs' : 'convert.ts'),
        EZBIDS_DEFACE_PATH: path.join(ezbidsHandlerDir, ENVIRONMENT === 'production' ? 'deface.cjs' : 'deface.ts'),
        EZBIDS_TEMPLATE_DIR: path.join(ezbidsHandlerDir, 'templates'),
        EZBIDS_BACKEND_DIR: ezbidsBackendDir,
        BIDS_VALIDATOR_PATH: bidsValidatorPath,
        EZBIDS_PLATFORM: getEzBidsPlatform(),
        EZBIDS_ARCH: getEzBidsArch(),
        ENVIRONMENT: ENVIRONMENT,
        ELECTRON_RUN_AS_NODE: '1',
        ...rendererEnv,
    };

    console.log('STARTING EZBIDS DESKTOP WITH ENV:', env);

    await startBackend(port, env);
    await startHandler(env);
    await startFrontend();
}

const treeKillAsync = (pid: number, name: string): Promise<void> =>
    new Promise((resolve) => {
        console.log(`tree-kill ${name} (pid ${pid})`);
        treeKill(pid, 'SIGTERM', (err) => {
            if (err) console.log(`tree-kill ${name} error:`, err);
            resolve();
        });
    });

function killAll(): Promise<void> {
    const jobs: Promise<void>[] = [];
    if (backendProcess?.pid) {
        const pid = backendProcess.pid;
        backendProcess = null;
        jobs.push(treeKillAsync(pid, 'backend'));
    }
    if (handlerProcess?.pid) {
        const pid = handlerProcess.pid;
        handlerProcess = null;
        jobs.push(treeKillAsync(pid, 'handler'));
    }
    return jobs.length ? Promise.all(jobs).then(() => undefined) : Promise.resolve();
}

app.whenReady().then(async () => {
    // This has to be inside of the app.whenReady() block to ensure that we can take control of the
    // SIGINT signal and it isnt hijacked by npm or electron itself
    process.on('SIGINT', () => {
        console.log('SIGINT received');
        app.quit();
    });

    await startApp();
});

process.on('SIGTERM', () => app.quit()); // let before-quit handle it

process.on('uncaughtException', (err) => {
    console.error('Uncaught exception:', err);
    void killAll().finally(() => process.exit(1));
});

app.on('before-quit', (event) => {
    if (handlerProcess || backendProcess) {
        event.preventDefault();
        void killAll().then(() => setImmediate(() => app.quit()));
    }
});

app.on('window-all-closed', () => app.quit());
