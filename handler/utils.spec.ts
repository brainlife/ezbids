import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';

jest.mock('execa', () => ({ execa: jest.fn() }));

import { getPythonExecutablePath, nodeArgsForScript, pet2bidsEnv, resolveHandlerScript } from './utils';

describe('handler script resolution (web handler runs .ts from source; desktop runs bundled .cjs)', () => {
    let dir: string;
    beforeEach(() => {
        dir = fs.mkdtempSync(path.join(os.tmpdir(), 'ezbids-utils-'));
    });
    afterEach(() => fs.rmSync(dir, { recursive: true, force: true }));

    it('uses the env override first', () => {
        expect(resolveHandlerScript('bids', dir, { EZBIDS_BIDS_PATH: '/x/bids.cjs' })).toBe('/x/bids.cjs');
    });

    it('prefers a built .js, else the .ts source', () => {
        expect(resolveHandlerScript('preprocess', dir, {})).toBe(path.join(dir, 'preprocess.ts'));
        fs.writeFileSync(path.join(dir, 'preprocess.js'), '');
        expect(resolveHandlerScript('preprocess', dir, {})).toBe(path.join(dir, 'preprocess.js'));
    });

    it('runs .ts scripts through ts-node-dev and bundled scripts as is', () => {
        const ts = nodeArgsForScript(['/h/bids.ts', '/w'], { EZBIDS_HANDLER_DIR: '/h' });
        expect(ts[0]).toMatch(/ts-node-dev[\\/]lib[\\/]bin\.js$/);
        expect(ts).toContain('--transpile-only');
        expect(ts).not.toContain('--watch');
        expect(ts.slice(-2)).toEqual(['/h/bids.ts', '/w']);

        expect(nodeArgsForScript(['/h/bids.cjs', '/w'], { EZBIDS_HANDLER_DIR: '/h' })).toEqual(['/h/bids.cjs', '/w']);

        const dev = nodeArgsForScript(['/h/bids.ts'], { EZBIDS_HANDLER_DIR: '/h', ENVIRONMENT: 'development' });
        expect(dev).toContain('--watch');
    });
});

describe('python (bundled runtime on the desktop, system python3 in the web image)', () => {
    const saved = { ...process.env };
    afterEach(() => {
        process.env = { ...saved };
    });

    it('uses python3 when there is no bundled runtime', () => {
        delete process.env.EZBIDS_BIN_DIR;
        delete process.env.EZBIDS_PYTHON;
        expect(getPythonExecutablePath()).toBe('python3');
        process.env.EZBIDS_BIN_DIR = '/nonexistent-bin-dir';
        expect(getPythonExecutablePath()).toBe('python3');
    });

    it('uses the bundled runtime when it exists', () => {
        const bin = fs.mkdtempSync(path.join(os.tmpdir(), 'ezbids-bin-'));
        fs.mkdirSync(path.join(bin, 'python-runtime'));
        process.env.EZBIDS_BIN_DIR = bin;
        process.env.EZBIDS_PLATFORM = 'darwin';
        expect(getPythonExecutablePath()).toBe(path.join(bin, 'python-runtime', 'python', 'bin', 'python3'));
        fs.rmSync(bin, { recursive: true, force: true });
    });
});

describe('pet2bidsEnv (pypet2bids uses our pinned dcm2niix)', () => {
    it('gives each run its own HOME, our dcm2niix first on PATH and in DCM2NIIX_PATH', () => {
        const base = fs.mkdtempSync(path.join(os.tmpdir(), 'ezbids-p2b-'));
        const ours = path.join(base, 'dcm2niix-linux-amd64');
        fs.writeFileSync(ours, '#!/bin/sh\n', { mode: 0o755 });
        const a = pet2bidsEnv(ours, base);
        const b = pet2bidsEnv(ours, base);
        expect(a.env.HOME).not.toBe(b.env.HOME); // parallel runs never share a config
        expect(a.env.HOME).toBe(a.env.USERPROFILE);
        expect(fs.existsSync(path.join(a.env.HOME as string, '.pet2bidsconfig'))).toBe(false);
        expect(a.env.DCM2NIIX_PATH).toBe(ours);
        const first = (a.env.PATH as string).split(path.delimiter)[0];
        if (process.platform !== 'win32') expect(fs.readlinkSync(path.join(first, 'dcm2niix'))).toBe(ours);
        a.cleanup();
        expect(fs.existsSync(a.env.HOME as string)).toBe(false);
        b.cleanup();
        fs.rmSync(base, { recursive: true, force: true });
    });
    it('changes nothing without a dcm2niix', () => {
        expect(pet2bidsEnv(undefined).env).toEqual({});
    });
});
