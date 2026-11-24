import { execa, Options } from 'execa';
import * as path from 'path';
import * as fs from 'fs';
import * as os from 'os';

/** Resolved path to `<EZBIDS_BIN_DIR>/<tool>` (e.g. 7z, dcm2niix, python-runtime). Callers add executable names and `.exe` where needed. */
export function getBinPath(tool: string): string {
    const binDir = process.env.EZBIDS_BIN_DIR;
    if (binDir) {
        return path.resolve(path.join(binDir, tool));
    }
    return tool;
}
/**
 * The desktop app ships a python runtime at $EZBIDS_BIN_DIR/python-runtime; the web handler image
 * (handler/Dockerfile) has no such folder and uses its own python3 (EZBIDS_PYTHON overrides it).
 */
export function hasBundledPython(): boolean {
    return !!process.env.EZBIDS_BIN_DIR && fs.existsSync(getBinPath('python-runtime'));
}

/** python3 inside the bundled runtime, or the system python3 when there is no bundled runtime. */
export function getPythonExecutablePath(): string {
    if (!hasBundledPython()) return process.env.EZBIDS_PYTHON ?? 'python3';
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

/** Our dcm2niix (bundled / image layout) first, so pypet2bids and ezBIDS_core never pick up another one. */
function getPythonDcm2niixPath(): string | undefined {
    const hasBundledEnv = !!(process.env.EZBIDS_BIN_DIR && process.env.EZBIDS_PLATFORM && process.env.EZBIDS_ARCH);
    if (hasBundledEnv) {
        const bundledDcm2niix = getDcm2niixExecutablePath();
        if (fs.existsSync(bundledDcm2niix)) return bundledDcm2niix;
    }
    return process.env.DCM2NIIX_PATH || undefined;
}

// in the future, if we want some sort of more sophisticated logging, we can replace this function
export function log(msg: string): void {
    // eslint-disable-next-line no-console -- CLI output
    console.log(msg);
}

/**
 * Environment that makes pypet2bids use our dcm2niix (the pinned one in handler/dcm2niix.env) on every platform.
 * pypet2bids looks in ~/.pet2bidsconfig first, then (posix) for `dcm2niix` on PATH, then DCM2NIIX_PATH from the
 * environment (Windows: config, then DCM2NIIX_PATH). So a user's own config or dcm2niix could win: each run gets
 * a fresh HOME (USERPROFILE) of its own with no config (pypet2bids writes its DEFAULT_METADATA_JSON there; runs
 * are parallel, so they must not share one), PATH starts with a folder whose `dcm2niix` is ours, and
 * DCM2NIIX_PATH is ours. Call cleanup() when the run is over.
 */
export function pet2bidsEnv(
    dcm2niix: string | undefined,
    baseDir: string = os.tmpdir()
): { env: NodeJS.ProcessEnv; cleanup: () => void } {
    if (!dcm2niix) return { env: {}, cleanup: () => undefined };
    const home = fs.mkdtempSync(path.join(baseDir, 'ezbids-pet2bids-'));
    const bin = path.join(home, 'bin');
    fs.mkdirSync(bin);
    if (process.platform !== 'win32') fs.symlinkSync(dcm2niix, path.join(bin, 'dcm2niix'));
    return {
        env: {
            HOME: home,
            USERPROFILE: home,
            DCM2NIIX_PATH: dcm2niix,
            PATH: `${bin}${path.delimiter}${process.env.PATH ?? ''}`,
        },
        cleanup: () => fs.rmSync(home, { recursive: true, force: true }),
    };
}

export async function runPython(
    argv: string[],
    opts: Options & { pet2bids?: boolean }
): Promise<{ status: number; stderr: string }> {
    const pythonRoot = getBinPath('python-runtime');
    const pythonExe = getPythonExecutablePath();
    const pythonDcm2niixPath = getPythonDcm2niixPath();
    const { pet2bids, ...execOpts } = opts;
    const p2b = pet2bids ? pet2bidsEnv(pythonDcm2niixPath) : { env: {}, cleanup: () => undefined };
    const withTimeout = opts.timeout !== undefined && opts.timeout !== null;
    let result;
    try {
        result = await execa(pythonExe, argv, {
            ...execOpts,
            ...(withTimeout ? { timeout: opts.timeout, stdio: 'pipe' as const } : { stdio: 'inherit' as const }),
            env: {
                ...process.env,
                ...(hasBundledPython()
                    ? {
                          PYTHONPATH: getBundledPythonSitePackages(),
                          PYTHONHOME: path.resolve(path.join(pythonRoot, 'python')),
                      }
                    : {}),
                ...(pythonDcm2niixPath ? { DCM2NIIX_PATH: pythonDcm2niixPath } : {}),
                ...p2b.env,
            },
        });
    } finally {
        p2b.cleanup();
    }
    const status = result.exitCode ?? -1;
    const stderr = withTimeout ? (result?.stderr?.toString() ?? '') : '';
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

/**
 * Node arguments to run a handler script: a .ts script (the web handler runs from source, and so does
 * the desktop app in development) goes through ts-node-dev; a bundled .js/.cjs script runs as is.
 */
export function nodeArgsForScript(args: string[], env: NodeJS.ProcessEnv = process.env): string[] {
    const scriptArgs = [...args];
    const isTypeScript = /\.ts$/.test(scriptArgs[0] ?? '');
    if (env.ENVIRONMENT === 'development' || isTypeScript) {
        const handlerDir = env.EZBIDS_HANDLER_DIR ?? __dirname;
        const tsNodeDevBin = require.resolve('ts-node-dev/lib/bin.js');
        const watch = env.ENVIRONMENT === 'development' ? ['--debounce', '2000', '--watch', handlerDir] : [];
        scriptArgs.unshift(tsNodeDevBin, '--transpile-only', ...watch, '-P', path.join(handlerDir, 'tsconfig.json'));
    }
    return scriptArgs;
}

/** A handler script by name: $EZBIDS_<NAME>_PATH, else <handlerDir>/<name>.js when built, else <name>.ts. */
export function resolveHandlerScript(name: string, handlerDir: string, env: NodeJS.ProcessEnv = process.env): string {
    const override = env[`EZBIDS_${name.toUpperCase()}_PATH`];
    if (override) return override;
    const js = path.join(handlerDir, `${name}.js`);
    return fs.existsSync(js) ? js : path.join(handlerDir, `${name}.ts`);
}

export async function runNodeScript(args: string[], opts?: Options): Promise<{ status: number; stderr: string }> {
    const scriptArgs = nodeArgsForScript(args);

    const result = await execa(process.execPath, scriptArgs, {
        stdio: 'inherit',
        reject: true,
        ...(opts ?? {}),
    });

    const status = result.exitCode ?? -1;
    const stderr = result?.stderr?.toString() ?? '';
    return { status, stderr };
}
