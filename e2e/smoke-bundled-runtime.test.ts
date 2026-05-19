/**
 * Layer 1 bundled-runtime smoke (opt-in via `EZBIDS_SMOKE_BUNDLED=1`).
 * CI runs `npm run smoke:bundled` after `fetch-binaries.sh`. Not part of default `npm test` (see jest.config.cjs testMatch).
 *
 * `EZBIDS_PLATFORM` / `EZBIDS_ARCH` must match the assets from `fetch-binaries.sh` (e.g. linux+amd64 on ubuntu-latest).
 */
import { spawnSync } from 'node:child_process';
import * as fs from 'fs';
import * as path from 'path';
import {
    getBinPath,
    getDcm2niixExecutablePath,
    getPythonExecutablePath,
    getRunPythonSubprocessEnv,
} from '../handler/envPaths';

const SMOKE = process.env.EZBIDS_SMOKE_BUNDLED === '1';
const REQUIRED_ENV = ['EZBIDS_BIN_DIR', 'EZBIDS_PLATFORM', 'EZBIDS_ARCH'] as const;

function runCmd(file: string, args: string[], env: NodeJS.ProcessEnv): { stdout: string; stderr: string; status: number | null; error?: Error } {
    const r = spawnSync(file, args, { env, encoding: 'utf8' });
    return { stdout: r.stdout ?? '', stderr: r.stderr ?? '', status: r.status, error: r.error };
}

function expectSuccess(file: string, args: string[], env: NodeJS.ProcessEnv, label: string): void {
    const { status, stdout, stderr, error } = runCmd(file, args, env);
    if (error) {
        throw new Error(`${label}: spawn failed: ${error.message}\nstdout:\n${stdout}\nstderr:\n${stderr}`);
    }
    if (status !== 0) {
        throw new Error(`${label} exited ${status}\nstdout:\n${stdout}\nstderr:\n${stderr}`);
    }
}

function assertExecutable(filePath: string): void {
    expect(fs.existsSync(filePath)).toBe(true);
    if (process.env.EZBIDS_PLATFORM === 'windows') {
        return;
    }
    expect(() => fs.accessSync(filePath, fs.constants.X_OK)).not.toThrow();
}

function sevenZExecutablePath(): string {
    const platform = process.env.EZBIDS_PLATFORM!;
    const arch = process.env.EZBIDS_ARCH!;
    const name = platform === 'windows' ? `7z-${platform}-${arch}.exe` : `7z-${platform}-${arch}`;
    return path.join(getBinPath('7z'), name);
}

function allineateExecutablePath(): string {
    const platform = process.env.EZBIDS_PLATFORM!;
    const arch = process.env.EZBIDS_ARCH!;
    const name = platform === 'windows' ? `allineate-${platform}-${arch}.exe` : `allineate-${platform}-${arch}`;
    return path.join(getBinPath('allineate'), name);
}

const describeSmoke = SMOKE ? describe : describe.skip;

describeSmoke('Layer 1: bundled runtime smoke', () => {
    beforeAll(() => {
        const missing = REQUIRED_ENV.filter((k) => !process.env[k]);
        if (missing.length > 0) {
            throw new Error(
                `Layer 1 smoke requires: ${missing.join(', ')}. CI should set these after fetch-binaries.sh.`
            );
        }
    });

    describe('resolved bundled binaries', () => {
        it('python interpreter exists and is executable', () => {
            assertExecutable(getPythonExecutablePath());
        });

        it('dcm2niix exists at getDcm2niixExecutablePath() and runs --version', () => {
            const dcm = getDcm2niixExecutablePath();
            assertExecutable(dcm);
            const { status, stdout, stderr, error } = runCmd(dcm, ['--version'], { ...process.env });
            if (error) {
                throw new Error(`dcm2niix --version spawn: ${error.message}`);
            }
            expect(status).toBe(0);
            expect(`${stdout}${stderr}`.toLowerCase()).toMatch(/dcm2niix|dcm2nii/);
        });

        it('7z exists at expand.utils path and is executable', () => {
            const sevenZ = sevenZExecutablePath();
            assertExecutable(sevenZ);
            if (process.env.EZBIDS_PLATFORM === 'windows') {
                const dll = path.join(path.dirname(sevenZ), '7z.dll');
                expect(fs.existsSync(dll)).toBe(true);
            }
        });

        it('allineate binary exists when bundle ships allineate', () => {
            const dir = getBinPath('allineate');
            if (!fs.existsSync(dir)) {
                return;
            }
            assertExecutable(allineateExecutablePath());
        });

        it('PYTHONHOME and site-packages directories exist', () => {
            const env = getRunPythonSubprocessEnv();
            expect(env.PYTHONHOME && fs.existsSync(env.PYTHONHOME)).toBe(true);
            expect(env.PYTHONPATH && fs.existsSync(env.PYTHONPATH)).toBe(true);
        });

        it('BIDS validator script is on disk (Layer 2 preprocess contract)', () => {
            const fromEnv = process.env.BIDS_VALIDATOR_PATH;
            const p =
                fromEnv && fromEnv.length > 0
                    ? fromEnv
                    : (require.resolve('bids-validator/bin/bids-validator') as string);
            expect(fs.existsSync(p)).toBe(true);
        });
    });

    describe('DCM2NIIX_PATH handling matches handler/envPaths', () => {
        it('injects bundled dcm2niix when EZBIDS_* set, file on disk, and DCM2NIIX_PATH unset', () => {
            const bundled = getDcm2niixExecutablePath();
            expect(fs.existsSync(bundled)).toBe(true);
            const prev = process.env.DCM2NIIX_PATH;
            delete process.env.DCM2NIIX_PATH;
            try {
                const env = getRunPythonSubprocessEnv();
                expect(env.DCM2NIIX_PATH).toBe(bundled);
            } finally {
                if (prev !== undefined) {
                    process.env.DCM2NIIX_PATH = prev;
                }
            }
        });

        it('honours explicit DCM2NIIX_PATH when set', () => {
            const bundled = getDcm2niixExecutablePath();
            const prev = process.env.DCM2NIIX_PATH;
            process.env.DCM2NIIX_PATH = bundled;
            try {
                const env = getRunPythonSubprocessEnv();
                expect(env.DCM2NIIX_PATH).toBe(bundled);
            } finally {
                if (prev === undefined) {
                    delete process.env.DCM2NIIX_PATH;
                } else {
                    process.env.DCM2NIIX_PATH = prev;
                }
            }
        });
    });

    describe('bundled python + PET entrypoints', () => {
        it('imports pypet2bids with getRunPythonSubprocessEnv()', () => {
            const py = getPythonExecutablePath();
            expectSuccess(py, ['-c', 'import pypet2bids'], getRunPythonSubprocessEnv(), 'import pypet2bids');
        });

        it('imports pypet2bids with explicit DCM2NIIX_PATH in process.env', () => {
            const bundled = getDcm2niixExecutablePath();
            const prev = process.env.DCM2NIIX_PATH;
            process.env.DCM2NIIX_PATH = bundled;
            try {
                const py = getPythonExecutablePath();
                expectSuccess(py, ['-c', 'import pypet2bids'], getRunPythonSubprocessEnv(), 'import pypet2bids (explicit DCM2NIIX_PATH)');
            } finally {
                if (prev === undefined) {
                    delete process.env.DCM2NIIX_PATH;
                } else {
                    process.env.DCM2NIIX_PATH = prev;
                }
            }
        });

        it('python -m dcm2niix4pet --help exits 0', () => {
            const py = getPythonExecutablePath();
            expectSuccess(py, ['-m', 'dcm2niix4pet', '--help'], getRunPythonSubprocessEnv(), 'dcm2niix4pet --help');
        });

        it('python -m ecatpet2bids --help exits 0', () => {
            const py = getPythonExecutablePath();
            expectSuccess(py, ['-m', 'ecatpet2bids', '--help'], getRunPythonSubprocessEnv(), 'ecatpet2bids --help');
        });
    });
});
