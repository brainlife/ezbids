/**
 * Which defacing methods this handler can run, from the tools it actually finds:
 * - allineate: the bundled allineate binary and its face-mask templates (desktop, and the web image)
 * - quickshear: ROBEX (runROBEX.sh) + quickshear + FSL's fslreorient2std (web image, as on master)
 * - pydeface: pydeface + FSL (web image, as on master)
 * The desktop app cannot ship FSL or ROBEX, so there it is allineate only; nothing here is a hard-coded list.
 * The handler writes the result to <workdir>/deface-methods.json at start; the API serves it to the UI.
 */
import * as fs from 'fs';
import * as path from 'path';

export type DefaceMethod = 'quickshear' | 'pydeface' | 'allineate';
export const DEFACE_METHODS_FILE = 'deface-methods.json';

/** First match of `cmd` on PATH (plain executable check, no shell). */
export function onPath(cmd: string, env: NodeJS.ProcessEnv = process.env): string | undefined {
    const exts = process.platform === 'win32' ? ['.exe', '.cmd', '.bat', ''] : [''];
    for (const dir of (env.PATH ?? '').split(path.delimiter)) {
        if (!dir) continue;
        for (const ext of exts) {
            const p = path.join(dir, cmd + ext);
            try {
                fs.accessSync(p, fs.constants.X_OK);
                if (fs.statSync(p).isFile()) return p;
            } catch {
                // not here
            }
        }
    }
    return undefined;
}

export function allineatePath(env: NodeJS.ProcessEnv = process.env): string {
    const platform = env.EZBIDS_PLATFORM;
    const arch = env.EZBIDS_ARCH;
    const name = platform === 'windows' ? `allineate-${platform}-${arch}.exe` : `allineate-${platform}-${arch}`;
    const binDir = env.EZBIDS_BIN_DIR;
    return path.resolve(binDir ? path.join(binDir, 'allineate', name) : path.join('allineate', name));
}

export function templateDir(env: NodeJS.ProcessEnv = process.env): string {
    return env.EZBIDS_TEMPLATE_DIR ?? path.join(__dirname, 'templates');
}

/** Methods in the order the UI offers them (master's quickshear first when present). */
export function availableDefaceMethods(env: NodeJS.ProcessEnv = process.env): DefaceMethod[] {
    const methods: DefaceMethod[] = [];
    // the desktop app is allineate only, even where FSL/ROBEX happen to be installed: the app does not ship them,
    // so a conversion must not depend on what a given computer has on its PATH
    const fsl = env.IS_ELECTRON !== 'true' && !!onPath('fslreorient2std', env);
    if (fsl && onPath('runROBEX.sh', env) && onPath('quickshear', env)) methods.push('quickshear');
    if (fsl && onPath('pydeface', env)) methods.push('pydeface');
    const tpl = templateDir(env);
    if (
        fs.existsSync(allineatePath(env)) &&
        fs.existsSync(path.join(tpl, 'mean_reg2mean.nii.gz')) &&
        fs.existsSync(path.join(tpl, 'facemask.nii.gz'))
    ) {
        methods.push('allineate');
    }
    return methods;
}

/** Written by the handler at start; read by the API (GET /deface-methods). */
export function writeDefaceMethods(workdir: string, env: NodeJS.ProcessEnv = process.env): DefaceMethod[] {
    const methods = availableDefaceMethods(env);
    fs.mkdirSync(workdir, { recursive: true });
    fs.writeFileSync(path.join(workdir, DEFACE_METHODS_FILE), JSON.stringify({ methods }));
    return methods;
}
