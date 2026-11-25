/**
 * The environment the desktop app gives its backend, handler and aimport engine. No electron import: the packaged
 * smoke test (test/smoke-test-aimport.ts) builds the same env from the same function.
 */
import path from 'path';

export interface DesktopEnvOptions {
    base: NodeJS.ProcessEnv;
    production: boolean;
    /** a path inside the app (production: Resources/app; development: the repo) */
    projectPath: (...segments: string[]) => string;
    binDir: string;
    userDataPath: string;
    port: number;
    platform: string;
    arch: string;
    rendererEnv: Record<string, string>;
}

export function desktopEnv(o: DesktopEnvOptions): NodeJS.ProcessEnv {
    const ENVIRONMENT = o.production ? 'production' : 'development';
    const ext = (name: string): string => `${name}.${o.production ? 'cjs' : 'ts'}`;
    const ezbidsHandlerDir = o.production ? o.projectPath('dist', 'handler') : o.projectPath('handler');
    return {
        ...o.base,
        USER_DATA_PATH: o.userDataPath,
        UPLOAD_DIR: path.join(o.userDataPath, 'upload'),
        WORKDIR: path.join(o.userDataPath, 'workdir'),
        PORT: String(o.port),
        MONGO_CONNECTION_STRING: '',
        EZBIDS_BIN_DIR: o.binDir,
        EZBIDS_HANDLER_DIR: ezbidsHandlerDir,
        PRELOAD_DIR: o.production ? o.projectPath('dist') : o.projectPath('electron'),
        EZBIDS_PREPROCESS_PATH: path.join(ezbidsHandlerDir, ext('preprocess')),
        EZBIDS_EXPAND_PATH: path.join(ezbidsHandlerDir, ext('expand')),
        EZBIDS_BIDS_PATH: path.join(ezbidsHandlerDir, ext('bids')),
        EZBIDS_CONVERT_PATH: path.join(ezbidsHandlerDir, ext('convert')),
        EZBIDS_DEFACE_PATH: path.join(ezbidsHandlerDir, ext('deface')),
        EZBIDS_TEMPLATE_DIR: path.join(ezbidsHandlerDir, 'templates'),
        EZBIDS_BACKEND_DIR: o.production ? o.projectPath('dist') : o.projectPath('api'),
        BIDS_VALIDATOR_PATH: o.projectPath('node_modules', 'bids-validator', 'bin', 'bids-validator'),
        EZBIDS_PLATFORM: o.platform,
        EZBIDS_ARCH: o.arch,
        ENVIRONMENT,
        ELECTRON_RUN_AS_NODE: '1',
        ...o.rendererEnv,
    };
}
