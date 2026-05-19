/**
 * Bundled-tool paths under `EZBIDS_BIN_DIR` and env for bundled-python subprocesses (no execa).
 * Used by {@link ./utils} `runPython` and by Layer 1 smoke tests.
 */
import * as fs from 'fs';
import * as path from 'path';

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
    const pythonRoot = getBinPath('python-runtime');
    const pyBin =
        process.env.EZBIDS_PLATFORM === 'windows'
            ? path.join(pythonRoot, 'python', 'python.exe')
            : path.join(pythonRoot, 'python', 'bin', 'python3');
    return path.resolve(pyBin);
}

function getBundledPythonSitePackages(): string {
    const pythonRoot = getBinPath('python-runtime');
    const sitePackages =
        process.env.EZBIDS_PLATFORM === 'windows'
            ? path.join(pythonRoot, 'venv', 'Lib', 'site-packages')
            : path.join(pythonRoot, 'venv', 'lib', 'python3.8', 'site-packages');
    return path.resolve(sitePackages);
}

export function getDcm2niixExecutablePath(): string {
    const platform = process.env.EZBIDS_PLATFORM;
    const arch = process.env.EZBIDS_ARCH;
    const base = `dcm2niix-${platform}-${arch}`;
    const fileName = platform === 'windows' ? `${base}.exe` : base;
    return path.resolve(path.join(getBinPath('dcm2niix'), fileName));
}

function getPythonDcm2niixPath(): string | undefined {
    if (process.env.DCM2NIIX_PATH) {
        return process.env.DCM2NIIX_PATH;
    }
    const hasBundledEnv = !!(process.env.EZBIDS_BIN_DIR && process.env.EZBIDS_PLATFORM && process.env.EZBIDS_ARCH);
    if (!hasBundledEnv) {
        return undefined;
    }
    const bundledDcm2niix = getDcm2niixExecutablePath();
    return fs.existsSync(bundledDcm2niix) ? bundledDcm2niix : undefined;
}

/** Environment passed to bundled-python subprocesses; must stay aligned with {@link ./utils} `runPython`. */
export function getRunPythonSubprocessEnv(): NodeJS.ProcessEnv {
    const pythonRoot = getBinPath('python-runtime');
    const pythonDcm2niixPath = getPythonDcm2niixPath();
    return {
        ...process.env,
        PYTHONPATH: getBundledPythonSitePackages(),
        PYTHONHOME: path.resolve(path.join(pythonRoot, 'python')),
        ...(pythonDcm2niixPath ? { DCM2NIIX_PATH: pythonDcm2niixPath } : {}),
    };
}
