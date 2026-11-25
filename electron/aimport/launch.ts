/**
 * How the aimport engine is started: its python, argv, env and folders. No electron import: engine.ts spawns
 * what this returns, and the packaged smoke test (test/smoke-test-aimport.ts) spawns the very same thing.
 */
import crypto from 'crypto';
import fs from 'fs';
import net from 'net';
import path from 'path';
import type { SpawnOptions } from 'child_process';

export interface AimportContext {
    env: NodeJS.ProcessEnv;
    appDir: string;
    userDataPath: string;
    isPackaged: boolean;
    resourcesPath: string;
    platform: string;
    arch: string;
    binDir: string;
    /** the binary that runs preprocess.cjs as node (Electron with ELECTRON_RUN_AS_NODE); default process.execPath */
    execPath?: string;
}

export interface AimportLaunch {
    command: string;
    args: string[];
    options: SpawnOptions;
    port: number;
    token: string;
    inputDir: string;
    workDir: string;
}

export const freePort = (): Promise<number> =>
    new Promise((resolve, reject) => {
        const server = net.createServer();
        server.listen(0, '127.0.0.1', () => {
            const addr = server.address();
            const port = addr && typeof addr === 'object' ? addr.port : 0;
            server.close(() => (port ? resolve(port) : reject(new Error('could not get port'))));
        });
        server.on('error', reject);
    });

export const runtimeDir = (ctx: AimportContext): string =>
    ctx.isPackaged ? path.join(ctx.resourcesPath, 'aimport') : path.join(ctx.appDir, 'aimport', 'runtime');

export const pythonPath = (ctx: AimportContext): string =>
    ctx.platform === 'windows'
        ? path.join(runtimeDir(ctx), 'python', 'python.exe')
        : path.join(runtimeDir(ctx), 'python', 'bin', 'python3');

/** Folders, a free port and a fresh token for an engine on inputDir; nothing is started. */
export async function aimportLaunch(ctx: AimportContext, inputDir: string): Promise<AimportLaunch> {
    const resolved = path.resolve(inputDir);
    if (!fs.statSync(resolved).isDirectory()) throw new Error('not a folder');
    // one work folder per input folder, so a restart resumes that folder's plan; keys are shared per project
    const id = crypto.createHash('sha256').update(resolved).digest('hex').slice(0, 16);
    const base = path.join(ctx.userDataPath, 'aimport');
    const workDir = path.join(base, 'work', id);
    const keysDir = path.join(base, 'keys');
    fs.mkdirSync(workDir, { recursive: true });
    fs.mkdirSync(keysDir, { recursive: true, mode: 0o700 });

    const port = await freePort();
    const token = crypto.randomBytes(32).toString('hex');
    const handlerDir = path.join(ctx.appDir, 'dist', 'handler');
    const shim = ctx.isPackaged
        ? path.join(runtimeDir(ctx), 'aimport_desktop.py')
        : path.join(ctx.appDir, 'aimport', 'aimport_desktop.py');
    const exe = ctx.platform === 'windows' ? '.exe' : '';
    const env: NodeJS.ProcessEnv = {
        ...ctx.env,
        AIMPORT_TOKEN: token,
        AIMPORT_DESKTOP_RUNTIME: runtimeDir(ctx),
        AIMPORT_EZBIDS_HANDLER_DIR: handlerDir,
        // the desktop's ezBIDS preprocess, run by Electron as node (ELECTRON_RUN_AS_NODE is in ctx.env)
        AIMPORT_EZBIDS_ARGV: JSON.stringify([
            ctx.execPath ?? process.execPath,
            path.join(handlerDir, 'preprocess.cjs'),
        ]),
        AIMPORT_ALLINEATE: path.join(ctx.binDir, 'allineate', `allineate-${ctx.platform}-${ctx.arch}${exe}`),
        EZBIDS_EXPAND_PATH: path.join(handlerDir, 'expand.cjs'),
        EZBIDS_TEMPLATE_DIR: path.join(handlerDir, 'templates'),
        ENVIRONMENT: 'production', // ezBIDS scripts are the built .cjs, also in dev
        ELECTRON_RUN_AS_NODE: '1',
    };
    delete env.AIMPORT_IN_CONTAINER;

    // -I: ignore the user's PYTHON* settings and site dir; -B: never write .pyc into the (signed) app bundle
    const args = [
        '-I',
        '-B',
        shim,
        'serve',
        '--input',
        resolved,
        '--work',
        workDir,
        '--keys',
        keysDir,
        '--host',
        '127.0.0.1',
        '--port',
        String(port),
    ];
    return {
        command: pythonPath(ctx),
        args,
        options: { env, stdio: 'inherit', detached: ctx.platform !== 'windows' },
        port,
        token,
        inputDir: resolved,
        workDir,
    };
}
