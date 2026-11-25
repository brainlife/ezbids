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
import path from 'path';
import treeKill from 'tree-kill';
import { AimportContext, aimportLaunch } from './launch';

export type { AimportContext } from './launch';

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
    const launch = await aimportLaunch(ctx, inputDir);
    const { port, token, workDir } = launch;
    const proc = spawn(launch.command, launch.args, launch.options);
    const started: Engine = { proc, port, token, inputDir: launch.inputDir, workDir };
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
        if (
            !API_METHODS.has(method) ||
            typeof apiPath !== 'string' ||
            !apiPath.startsWith('/') ||
            apiPath.startsWith('//')
        )
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
