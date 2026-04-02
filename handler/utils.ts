import { execa, Options } from 'execa';
import * as path from 'path';
import * as fs from 'fs';

export function getBinPath(binaryName: string): string {
    const binDir = process.env.EZBIDS_BIN_DIR;
    if (binDir) {
        const name =
            process.env.EZBIDS_PLATFORM === 'windows' && !binaryName.endsWith('.exe')
                ? `${binaryName}.exe`
                : binaryName;
        return path.resolve(path.join(binDir, name));
    }
    return binaryName;
}

/** Platform for binary naming: darwin | linux | windows. */
function getPlatform(): string {
    const env = process.env.EZBIDS_PLATFORM?.toLowerCase();
    if (env === 'darwin' || env === 'linux' || env === 'windows') return env;
    return process.env.EZBIDS_PLATFORM;
}

/** Arch for binary naming: amd64 | arm64. */
function getArch(): string {
    const env = process.env.EZBIDS_ARCH?.toLowerCase();
    if (env === 'amd64' || env === 'arm64') return env;
    return process.arch === 'arm64' ? 'arm64' : 'amd64';
}

/**
 * Returns the path to the dcm2niix executable for the current (or env-overridden) platform/arch.
 * Relies on EZBIDS_BIN_DIR; binary name follows fetch-binaries pattern: dcm2niix-<platform>-<arch>[.exe].
 */
export function getDcm2niixExecutablePath(): string {
    const binDir = process.env.EZBIDS_BIN_DIR;
    const platform = getPlatform();
    const arch = getArch();
    const base = `dcm2niix-${platform}-${arch}`;
    const name = platform === 'windows' ? `${base}.exe` : base;
    if (binDir) {
        return path.resolve(path.join(binDir, 'dcm2niix', name));
    }
    return path.join('dcm2niix', name);
}

// in the future, if we want some sort of more sophisticated logging, we can replace this function
export function log(msg: string): void {
    // eslint-disable-next-line no-console -- CLI output
    console.log(msg);
}

export async function runPython(argv: string[], opts: Options): Promise<{ status: number; stderr: string }> {
    const pythonHome = getBinPath('python-runtime');
    const withTimeout = opts.timeout !== undefined && opts.timeout !== null;
    const result = await execa(
        path.resolve(
            path.join(
                pythonHome,
                'python',
                'bin',
                process.env.EZBIDS_PLATFORM === 'windows' ? 'python3.exe' : 'python3'
            )
        ),
        argv,
        {
            ...opts,
            ...(withTimeout ? { timeout: opts.timeout, stdio: 'pipe' as const } : { stdio: 'inherit' as const }),
            env: {
                ...process.env,
                PYTHONPATH: path.join(getBinPath('python-runtime'), 'venv', 'lib', 'python3.8', 'site-packages'),
                PYTHONHOME: path.resolve(path.join(pythonHome, 'python')),
            },
        }
    );
    const status = result.exitCode ?? -1;
    const stderr = withTimeout ? result.stderr.toString() ?? '' : '';
    return { status, stderr };
}

export async function runBidsValidator(
    outputAsJson: boolean,
    pathToValidate: string,
    outLogFilePath: string
): Promise<{ hasErr: boolean }> {
    const validatorBin = process.env.BIDS_VALIDATOR_PATH;
    if (!validatorBin) throw new Error('BIDS_VALIDATOR_PATH is not set');
    const args = [validatorBin, pathToValidate];
    if (outputAsJson) {
        args.push('--json');
    }
    const result = await execa(process.execPath, args, {
        reject: false,
        all: true,
    });
    const content = result.all ?? result.stdout + result.stderr;
    fs.writeFileSync(outLogFilePath, content);
    const hasErr = /\bERR\b/.test(content);
    return { hasErr };
}
