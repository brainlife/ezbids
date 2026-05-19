import { execa, Options } from 'execa';
import * as path from 'path';
import * as fs from 'fs';
import { getPythonExecutablePath, getRunPythonSubprocessEnv } from './envPaths';

export { getBinPath, getDcm2niixExecutablePath, getPythonExecutablePath, getRunPythonSubprocessEnv } from './envPaths';

// in the future, if we want some sort of more sophisticated logging, we can replace this function
export function log(msg: string): void {
    // eslint-disable-next-line no-console -- CLI output
    console.log(msg);
}

export async function runPython(argv: string[], opts: Options): Promise<{ status: number; stderr: string }> {
    const pythonExe = getPythonExecutablePath();
    const withTimeout = opts.timeout !== undefined && opts.timeout !== null;
    const result = await execa(pythonExe, argv, {
        ...opts,
        ...(withTimeout ? { timeout: opts.timeout, stdio: 'pipe' as const } : { stdio: 'inherit' as const }),
        env: getRunPythonSubprocessEnv(),
    });
    const status = result.exitCode ?? -1;
    const stderr = withTimeout ? result?.stderr?.toString() ?? '' : '';
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

export async function runNodeScript(args: string[], opts?: Options): Promise<{ status: number; stderr: string }> {
    const scriptArgs = [...args];
    if (process.env.ENVIRONMENT === 'development') {
        const tsNodeDevBin = require.resolve('ts-node-dev/lib/bin.js');
        scriptArgs.unshift(
            tsNodeDevBin,
            '--transpile-only',
            '--debounce',
            '2000',
            '--watch',
            process.env.EZBIDS_HANDLER_DIR ?? '',
            '-P',
            path.join(process.env.EZBIDS_HANDLER_DIR ?? '', 'tsconfig.json')
        );
    }

    const result = await execa(process.execPath, scriptArgs, {
        stdio: 'inherit',
        reject: true,
        ...(opts ?? {}),
    });

    const status = result.exitCode ?? -1;
    const stderr = result?.stderr?.toString() ?? '';
    return { status, stderr };
}
