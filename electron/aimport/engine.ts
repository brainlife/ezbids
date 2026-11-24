/**
 * aimport engine sidecar: `python aimport_desktop.py serve` on a random 127.0.0.1 port with a fresh random token.
 *
 * The token never leaves the main process: the renderer calls the engine through the `aimport:api` IPC proxy,
 * and the QA viewer is opened here with the engine's one-time-code flow (/viewer/session), so no token and no
 * code is ever put in a URL the renderer sees. The engine is started when the person picks a folder (its --input
 * is fixed at start) and tree-killed with the other children.
 */
/* eslint-disable no-console */
import { BrowserWindow, dialog, IpcMain, shell, WebContentsView } from 'electron';
import { spawn, ChildProcess } from 'child_process';
import crypto from 'crypto';
import fs from 'fs';
import net from 'net';
import path from 'path';
import treeKill from 'tree-kill';

export interface AimportContext {
    env: NodeJS.ProcessEnv;
    appDir: string;
    userDataPath: string;
    isPackaged: boolean;
    resourcesPath: string;
    platform: string;
    arch: string;
    binDir: string;
}

interface Engine {
    proc: ChildProcess;
    port: number;
    token: string;
    inputDir: string;
    workDir: string;
}

let engine: Engine | null = null;
const API_METHODS = new Set(['GET', 'POST', 'PATCH']);

export const hasAimport = (): boolean => engine !== null;

const freePort = (): Promise<number> =>
    new Promise((resolve, reject) => {
        const server = net.createServer();
        server.listen(0, '127.0.0.1', () => {
            const addr = server.address();
            const port = addr && typeof addr === 'object' ? addr.port : 0;
            server.close(() => (port ? resolve(port) : reject(new Error('could not get port'))));
        });
        server.on('error', reject);
    });

const runtimeDir = (ctx: AimportContext): string =>
    ctx.isPackaged ? path.join(ctx.resourcesPath, 'aimport') : path.join(ctx.appDir, 'aimport', 'runtime');

const pythonPath = (ctx: AimportContext): string =>
    ctx.platform === 'windows'
        ? path.join(runtimeDir(ctx), 'python', 'python.exe')
        : path.join(runtimeDir(ctx), 'python', 'bin', 'python3');

export function stopAimport(): Promise<void> {
    closeViewer();
    const current = engine;
    engine = null;
    if (!current?.proc.pid) return Promise.resolve();
    const pid = current.proc.pid;
    return new Promise((resolve) => {
        console.log(`tree-kill aimport (pid ${pid})`);
        treeKill(pid, 'SIGTERM', (err) => {
            if (err) console.log('tree-kill aimport error:', err);
            resolve();
        });
    });
}

async function call(method: string, apiPath: string, body?: unknown): Promise<{ status: number; data: unknown }> {
    if (!engine) return { status: 503, data: { detail: 'the AI import engine is not running' } };
    const res = await fetch(`http://127.0.0.1:${engine.port}${apiPath}`, {
        method,
        headers: {
            Authorization: `Bearer ${engine.token}`,
            ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
        },
        body: body === undefined ? undefined : JSON.stringify(body),
    });
    const text = await res.text();
    let data: unknown = text;
    try {
        data = JSON.parse(text);
    } catch {
        /* not JSON */
    }
    return { status: res.status, data };
}

async function waitReady(timeoutMs = 30000): Promise<void> {
    const until = Date.now() + timeoutMs;
    while (Date.now() < until) {
        if (!engine) throw new Error('the AI import engine exited at start');
        try {
            if ((await call('GET', '/status')).status === 200) return;
        } catch {
            /* not listening yet */
        }
        await new Promise((r) => setTimeout(r, 300));
    }
    throw new Error('the AI import engine did not start in time');
}

async function startAimport(ctx: AimportContext, inputDir: string): Promise<Engine> {
    await stopAimport();
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
        AIMPORT_EZBIDS_ARGV: JSON.stringify([process.execPath, path.join(handlerDir, 'preprocess.cjs')]),
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
    const proc = spawn(pythonPath(ctx), args, {
        env,
        stdio: 'inherit',
        detached: ctx.platform !== 'windows',
    });
    const started: Engine = { proc, port, token, inputDir: resolved, workDir };
    engine = started;
    proc.on('error', (err) => console.error('aimport failed to start:', err));
    proc.on('exit', (code) => {
        console.log('aimport exited with', code);
        if (engine === started) engine = null;
    });
    await waitReady();
    return started;
}

// The QA viewer is a modal inside the main window: a WebContentsView laid over the AI import page's dialog body
// (the renderer reports that box). Sandboxed guest, no preload, no node; it stays on the engine's loopback origin.
interface Bounds {
    x: number;
    y: number;
    width: number;
    height: number;
}

let viewer: { view: WebContentsView; host: BrowserWindow } | null = null;

const toBounds = (b: Bounds): Bounds => ({
    x: Math.max(0, Math.round(Number(b?.x) || 0)),
    y: Math.max(0, Math.round(Number(b?.y) || 0)),
    width: Math.max(1, Math.round(Number(b?.width) || 1)),
    height: Math.max(1, Math.round(Number(b?.height) || 1)),
});

function closeViewer(): void {
    const current = viewer;
    viewer = null;
    if (!current) return;
    if (!current.host.isDestroyed()) current.host.contentView.removeChildView(current.view);
    if (!current.view.webContents.isDestroyed()) current.view.webContents.close();
}

function openViewer(host: BrowserWindow, url: string, bounds: Bounds): void {
    if (!engine || !/^\/viewer\/open\?code=[0-9a-f]{32}$/.test(url)) throw new Error('bad viewer url');
    closeViewer();
    const origin = `http://127.0.0.1:${engine.port}`;
    const inOrigin = (target: string): boolean => target.startsWith(`${origin}/`);
    const view = new WebContentsView({
        webPreferences: { contextIsolation: true, nodeIntegration: false, sandbox: true },
    });
    const wc = view.webContents;
    // no new windows: an engine-origin link opens in the modal itself, anything else is refused
    wc.setWindowOpenHandler(({ url: target }) => {
        if (inOrigin(target)) void wc.loadURL(target);
        return { action: 'deny' };
    });
    wc.on('will-navigate', (event, target) => {
        if (!inOrigin(target)) event.preventDefault();
    });
    wc.on('will-redirect', (event, target) => {
        if (!inOrigin(target)) event.preventDefault();
    });
    host.contentView.addChildView(view);
    view.setBounds(toBounds(bounds));
    viewer = { view, host };
    host.once('closed', () => {
        if (viewer?.view === view) viewer = null;
    });
    void wc.loadURL(origin + url);
}

export function registerAimportIpc(ipcMain: IpcMain, ctx: AimportContext): void {
    ipcMain.handle('aimport:pick-folder', async () => {
        const res = await dialog.showOpenDialog({ properties: ['openDirectory'] });
        return res.canceled || !res.filePaths.length ? null : res.filePaths[0];
    });
    ipcMain.handle('aimport:start', async (_e, inputDir: string) => {
        try {
            const started = await startAimport(ctx, inputDir);
            return { ok: true, inputDir: started.inputDir };
        } catch (err) {
            return { ok: false, error: String((err as Error).message ?? err) };
        }
    });
    ipcMain.handle('aimport:api', async (_e, method: string, apiPath: string, body?: unknown) => {
        if (!API_METHODS.has(method) || typeof apiPath !== 'string' || !apiPath.startsWith('/') || apiPath.startsWith('//'))
            return { status: 400, data: { detail: 'bad request' } };
        try {
            return await call(method, apiPath, body);
        } catch (err) {
            return { status: 503, data: { detail: String(err) } };
        }
    });
    ipcMain.handle('aimport:open-viewer', async (event, bounds: Bounds) => {
        const host = BrowserWindow.fromWebContents(event.sender);
        if (!host) return { ok: false, error: 'no window' };
        const res = await call('POST', '/viewer/session');
        if (res.status !== 200) return { ok: false, error: JSON.stringify(res.data) };
        openViewer(host, (res.data as { url: string }).url, bounds);
        return { ok: true };
    });
    ipcMain.handle('aimport:viewer-bounds', (event, bounds: Bounds) => {
        if (viewer && viewer.host.webContents === event.sender) viewer.view.setBounds(toBounds(bounds));
    });
    ipcMain.handle('aimport:close-viewer', () => closeViewer());
    ipcMain.handle('aimport:show-output', async () => {
        const res = await call('GET', '/status');
        const dir = (res.data as { output_dir?: string })?.output_dir;
        if (!engine || !dir || !path.resolve(dir).startsWith(engine.workDir + path.sep)) return { ok: false };
        await shell.openPath(dir);
        return { ok: true };
    });
    ipcMain.handle('aimport:stop', () => stopAimport());
}
