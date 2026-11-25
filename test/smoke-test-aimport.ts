/**
 * Headless end-to-end smoke test of a packed desktop app (electron-builder --dir), no window.
 *
 * Run by the packed app's own Electron binary as node, so process.execPath is what the app runs its scripts with:
 *   ELECTRON_RUN_AS_NODE=1 <packed ezBIDS executable> smoke-test-aimport.cjs <tmp_dir> <make-synthetic-dicom.py>
 * (test/smoke-test-aimport.sh builds this file with esbuild and finds the executable.)
 *
 * 1. writes a synthetic T1w DICOM series (the MNI152 2 mm template the app ships; made-up identifiers) with the
 *    bundled aimport python (test/make-synthetic-dicom.py)
 * 2. classic ezBIDS: runs the packed handler's preprocess.cjs on it as handler.ts does (same argv, cwd, env from
 *    electron/desktopEnv.ts) and checks ezBIDS_core.json lists an anat T1w
 * 3. aimport: starts the bundled engine exactly as electron/aimport/engine.ts does (aimportLaunch: same python,
 *    argv, env, random port, fresh token) and drives its API: scan -> plan -> approve (allineate defacing) ->
 *    execute -> status "validated"; then tree-kills it as the app does and checks the port is closed.
 */
/* eslint-disable no-console, @typescript-eslint/no-explicit-any, camelcase */
import { spawn, ChildProcess } from 'child_process';
import fs from 'fs';
import net from 'net';
import path from 'path';
import treeKill from 'tree-kill';
import { desktopEnv } from '../electron/desktopEnv';
import { AimportContext, aimportLaunch, pythonPath } from '../electron/aimport/launch';

function fail(msg: string): never {
    console.error(`smoke-test-aimport FAILED: ${msg}`);
    process.exit(1);
}

const tmp = path.resolve(process.argv[2] || fail('usage: smoke-test-aimport.cjs <tmp_dir> <make-synthetic-dicom.py>'));
const makeDicom = path.resolve(
    process.argv[3] || fail('usage: smoke-test-aimport.cjs <tmp_dir> <make-synthetic-dicom.py>')
);
const exe = process.execPath;
const platform = process.platform === 'win32' ? 'windows' : process.platform;
const arch = process.arch === 'arm64' ? 'arm64' : 'amd64';
const resourcesPath =
    platform === 'darwin' ? path.join(path.dirname(exe), '..', 'Resources') : path.join(path.dirname(exe), 'resources');
const appDir = path.join(resourcesPath, 'app');
const binDir = path.join(resourcesPath, 'bin');
const handlerDir = path.join(appDir, 'dist', 'handler');
const userDataPath = path.join(tmp, 'userData');

function step(msg: string): void {
    console.log(`\n==> ${msg}`);
}

function run(cmd: string, args: string[], opts: { env?: NodeJS.ProcessEnv; cwd?: string } = {}): Promise<number> {
    return new Promise((resolve, reject) => {
        const p = spawn(cmd, args, { stdio: 'inherit', ...opts });
        p.on('error', reject);
        p.on('exit', (code) => resolve(code ?? -1));
    });
}

const sleep = (ms: number): Promise<void> => new Promise((r) => setTimeout(r, ms));

function portOpen(port: number): Promise<boolean> {
    return new Promise((resolve) => {
        const s = net.connect(port, '127.0.0.1');
        s.once('connect', () => (s.destroy(), resolve(true)));
        s.once('error', () => resolve(false));
    });
}

function tail(file: string, lines = 60): string {
    try {
        return fs.readFileSync(file, 'utf8').split(/\r?\n/).slice(-lines).join('\n');
    } catch {
        return `(no ${file})`;
    }
}

const env = desktopEnv({
    base: process.env,
    production: true,
    projectPath: (...s) => path.join(appDir, ...s),
    binDir,
    userDataPath,
    port: 0,
    platform,
    arch,
    rendererEnv: { BRAINLIFE_AUTHENTICATION: 'false', IS_ELECTRON: 'true', API_HOST: 'http://localhost:0' },
});

const ctx: AimportContext = {
    env,
    appDir,
    userDataPath,
    isPackaged: true,
    resourcesPath,
    platform,
    arch,
    binDir,
    execPath: exe,
};

async function makeInput(dest: string): Promise<void> {
    step('synthetic T1w DICOM series');
    const code = await run(pythonPath(ctx), [
        '-I',
        '-B',
        makeDicom,
        path.join(handlerDir, 'templates', 'MNI152_T1_2mm.nii.gz'),
        path.join(dest, 'sub01', 'T1w'),
    ]);
    if (code !== 0) fail(`make-synthetic-dicom.py exited ${code}`);
}

async function classic(input: string): Promise<void> {
    step('classic ezBIDS preprocess (handler.ts argv: <execPath> preprocess.cjs <workdir> <handlerDir>)');
    const workdir = path.join(tmp, 'classic');
    fs.cpSync(input, workdir, { recursive: true });
    const code = await run(exe, [env.EZBIDS_PREPROCESS_PATH as string, workdir, handlerDir], { env, cwd: handlerDir });
    const corePath = path.join(workdir, 'ezBIDS_core.json');
    if (code !== 0 || !fs.existsSync(corePath))
        fail(`preprocess.cjs exited ${code}; ezBIDS_core.json: ${fs.existsSync(corePath)}`);
    const core = JSON.parse(fs.readFileSync(corePath, 'utf8'));
    const series: { type?: string; SeriesDescription?: string }[] = core.series ?? [];
    console.log(`ezBIDS_core.json: ${series.map((x) => `${x.SeriesDescription} -> ${x.type}`).join(', ')}`);
    if (!series.some((x) => x.type === 'anat/T1w')) fail('ezBIDS did not identify the synthetic T1w');
}

async function aimport(input: string): Promise<void> {
    step('aimport engine, started as electron/aimport/engine.ts does');
    const launch = await aimportLaunch(ctx, input);
    console.log(`${launch.command} ${launch.args.join(' ')}`);
    const proc: ChildProcess = spawn(launch.command, launch.args, launch.options);
    let exited: number | null | undefined;
    proc.on('exit', (code) => (exited = code));
    proc.on('error', (err) => fail(`engine failed to start: ${err}`));
    const base = `http://127.0.0.1:${launch.port}`;
    const call = async (method: string, p: string, body?: unknown): Promise<{ status: number; data: any }> => {
        const res = await fetch(base + p, {
            method,
            headers: {
                Authorization: `Bearer ${launch.token}`,
                ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
            },
            body: body === undefined ? undefined : JSON.stringify(body),
        });
        const text = await res.text();
        try {
            return { status: res.status, data: JSON.parse(text) };
        } catch {
            return { status: res.status, data: text };
        }
    };
    const stop = (): Promise<void> =>
        new Promise((resolve) => {
            if (!proc.pid || exited !== undefined) {
                resolve();
                return;
            }
            treeKill(proc.pid, 'SIGTERM', (err) => {
                if (err) console.log('tree-kill error:', err);
                resolve();
            });
        });
    const dump = (): void => {
        console.log('--- ezBIDS log (tail) ---\n' + tail(path.join(launch.workDir, 'ezbids.log')));
        for (const f of fs.readdirSync(launch.workDir)) console.log(`  work/${f}`);
    };
    const wait = async (timeoutMs: number): Promise<any> => {
        const until = Date.now() + timeoutMs;
        let last = '';
        while (Date.now() < until) {
            if (exited !== undefined) fail(`engine exited with ${exited}`);
            const s = (await call('GET', '/status')).data;
            const line = `${s.stage}: ${s.message ?? ''}`;
            if (line !== last) console.log(`  ${line}`);
            last = line;
            if (['idle', 'planned', 'validated', 'invalid', 'failed'].includes(s.stage)) return s;
            await sleep(1000);
        }
        throw new Error('timed out');
    };

    try {
        // ready, as engine.ts waitReady (30 s; slower first start on CI disks gets more)
        const until = Date.now() + 120000;
        for (;;) {
            if (exited !== undefined) fail(`engine exited with ${exited} at start`);
            try {
                if ((await call('GET', '/status')).status === 200) break;
            } catch {
                /* not listening yet */
            }
            if (Date.now() > until) fail('engine did not start in 120 s');
            await sleep(300);
        }
        const noToken = await fetch(`${base}/status`);
        if (noToken.status !== 401 && noToken.status !== 403) fail(`/status without the token gave ${noToken.status}`);

        step('POST /scan');
        const scan = await call('POST', '/scan', { project_id: 'ci-smoke' });
        if (scan.status !== 202) fail(`/scan: ${scan.status} ${JSON.stringify(scan.data)}`);
        const planned = await wait(15 * 60000);
        if (planned.stage !== 'planned') (dump(), fail(`scan ended ${JSON.stringify(planned)}`));

        const plan = (await call('GET', '/plan')).data;
        for (const e of plan.entries)
            console.log(`  entry ${e.id}: ${e.status} ${e.datatype}/${e.suffix} sub-${e.subject} deface=${e.deface}`);
        if (!plan.entries.some((e: any) => e.datatype === 'anat' && e.suffix === 'T1w' && e.status === 'ok'))
            fail('the plan has no anat/T1w entry');

        step('POST /approve (deface_method allineate) and /execute');
        const approve = await call('POST', '/approve', { deface_method: 'allineate' });
        if (approve.status !== 200) fail(`/approve: ${approve.status} ${JSON.stringify(approve.data)}`);
        const exec = await call('POST', '/execute');
        if (exec.status !== 202) fail(`/execute: ${exec.status} ${JSON.stringify(exec.data)}`);
        const done = await wait(20 * 60000);
        console.log(JSON.stringify({ ...done, manifest: undefined }, null, 1).slice(0, 4000));
        if (done.stage !== 'validated') (dump(), fail(`execute ended ${done.stage}`));
        const files = Object.values(done.manifest ?? {}).flat() as string[];
        console.log(`manifest: ${files.join(', ')}`);
        if (!files.some((f) => /anat\/.*_T1w\.nii(\.gz)?$/.test(f))) fail('no T1w in the manifest');
    } finally {
        step('tree-kill the engine (as stopAimport)');
        await stop();
    }
    for (let i = 0; i < 50 && (exited === undefined || (await portOpen(launch.port))); i++) await sleep(200);
    if (await portOpen(launch.port)) fail(`port ${launch.port} still open after tree-kill`);
    console.log(`engine stopped (exit ${exited}), port ${launch.port} closed`);
}

(async () => {
    console.log(`exe=${exe}\nresources=${resourcesPath}\nplatform=${platform} arch=${arch}`);
    fs.mkdirSync(tmp, { recursive: true });
    const input = path.join(tmp, 'input');
    await makeInput(input);
    await classic(input);
    await aimport(input);
    console.log('\nsmoke-test-aimport: all checks passed');
    process.exit(0);
})().catch((err) => fail(String(err?.stack ?? err)));
