import * as fs from 'fs';
import * as path from 'path';
import { spawnSync } from 'child_process';

export function walkDir(dir: string, files: string[]): void {
    const entries = fs.readdirSync(dir, { withFileTypes: true });
    for (const e of entries) {
        const full = path.join(dir, e.name);
        if (e.isDirectory()) {
            walkDir(full, files);
        } else if (e.isFile()) {
            files.push(full);
        }
    }
}

export function allFilesUnder(rootPath: string): string[] {
    const files: string[] = [];
    walkDir(rootPath, files);
    return files;
}

export function run(cmd: string, args: string[], opts?: { cwd?: string }): boolean {
    const r = spawnSync(cmd, args, {
        stdio: 'inherit',
        cwd: opts?.cwd,
    });
    return r.status === 0;
}

/**
 * Path to local 7z binary from ezbids-binaries, or '7z' to use system.
 * - With Electron: main process sets EZBIDS_BIN_DIR to the packaged resources/bin (or handler/bin in dev).
 * - Standalone: use handler/bin/ with name 7z-<platform>-<arch>, e.g. 7z-darwin-amd64.
 */
export function get7zPath(): string {
    const platform = process.platform; // 'darwin' | 'linux' | 'win32'
    const arch = process.arch === 'x64' ? 'amd64' : process.arch; // release uses amd64 not x64
    const name = `7z-${platform}-${arch}`;
    const binDir = process.env.EZBIDS_BIN_DIR || path.join(__dirname, 'bin');
    const localPath = path.join(binDir, name);
    if (fs.existsSync(localPath)) {
        return localPath;
    }
    return '7z';
}

export function rm(file: string): void {
    try {
        fs.unlinkSync(file);
    } catch (e) {
        console.error('rm failed:', file, e);
    }
}

/** Extract with 7z. If outDirName is given, extract into that subdir; otherwise extract in place. 7z -o has no space before path. */
export function extract7z(archivePath: string, cwd: string, outDirName?: string): boolean {
    const sevenZ = get7zPath();
    const base = path.basename(archivePath);
    const args = ['x', base];
    if (outDirName !== undefined) args.push(`-o${outDirName}`);
    return run(sevenZ, args, { cwd });
}
