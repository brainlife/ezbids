import { execa, Options } from 'execa';
import * as path from 'path';
import * as fs from 'fs';

/** Resolved path to `<EZBIDS_BIN_DIR>/<tool>` (e.g. 7z, dcm2niix, python-runtime). Callers add executable names and `.exe` where needed. */
export function getBinPath(tool: string): string {
    const binDir = process.env.EZBIDS_BIN_DIR;
    if (binDir) {
        return path.resolve(path.join(binDir, tool));
    }
    return tool;
}
/** python3 inside the bundled runtime, or a PATH fallback when EZBIDS_BIN_DIR is unset. */
export function getPythonExecutablePath(): string {
    const root = getBinPath('python-runtime');
    const pyBin =
        process.env.EZBIDS_PLATFORM === 'windows'
            ? path.join(root, 'python', 'python3.exe')
            : path.join(root, 'python', 'bin', 'python3');
    return path.resolve(pyBin);
}

function getBundledPythonSitePackages(): string {
    const root = getBinPath('python-runtime');
    const sitePackages =
        process.env.EZBIDS_PLATFORM === 'windows'
            ? path.join(root, 'venv', 'Lib', 'site-packages')
            : path.join(root, 'venv', 'lib', 'python3.8', 'site-packages');
    return path.resolve(sitePackages);
}

export function getDcm2niixExecutablePath(): string {
    const platform = process.env.EZBIDS_PLATFORM;
    const arch = process.env.EZBIDS_ARCH;
    const base = `dcm2niix-${platform}-${arch}`;
    const fileName = platform === 'windows' ? `${base}.exe` : base;
    return path.resolve(path.join(getBinPath('dcm2niix'), fileName));
}

// in the future, if we want some sort of more sophisticated logging, we can replace this function
export function log(msg: string): void {
    // eslint-disable-next-line no-console -- CLI output
    console.log(msg);
}

export async function runPython(argv: string[], opts: Options): Promise<{ status: number; stderr: string }> {
    const pythonRuntimeRoot = getBinPath('python-runtime');
    const pythonExe = getPythonExecutablePath();
    const withTimeout = opts.timeout !== undefined && opts.timeout !== null;
    const result = await execa(pythonExe, argv, {
        ...opts,
        ...(withTimeout ? { timeout: opts.timeout, stdio: 'pipe' as const } : { stdio: 'inherit' as const }),
        env: {
            ...process.env,
            PYTHONPATH: getBundledPythonSitePackages(),
            PYTHONHOME: path.resolve(path.join(pythonRuntimeRoot, 'python')),
        },
    });
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
