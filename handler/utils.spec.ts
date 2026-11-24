import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';

jest.mock('execa', () => ({ execa: jest.fn() }));

import { getPythonExecutablePath, nodeArgsForScript, resolveHandlerScript } from './utils';

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
