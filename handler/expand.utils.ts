import { execa, Options } from 'execa';
import * as fs from 'fs';
import * as path from 'path';
import { getBinPath } from './utils';

function formatFor7z(basename: string): string[] {
    if (basename.endsWith('.tar.gz') || basename.endsWith('.tgz')) return [];
    if (basename.endsWith('.gz')) return ['-tgzip'];
    if (basename.endsWith('.bz2')) return ['-tbzip2'];
    if (basename.endsWith('.zst')) return ['-tzstd'];
    return [];
}

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

export function rm(file: string): void {
    try {
        fs.unlinkSync(file);
    } catch (e) {
        console.error('rm failed:', file, e);
    }
}

export async function run7z(filePath: string, opts: Options, outDir?: string) {
    const platform = process.env.EZBIDS_PLATFORM;
    const arch = process.env.EZBIDS_ARCH;
    const sevenZName = platform === 'windows' ? `7z-${platform}-${arch}.exe` : `7z-${platform}-${arch}`;
    const sevenZPath = path.join(getBinPath('7z'), sevenZName);
    const args = ['x', '-y', ...formatFor7z(path.basename(filePath)), path.basename(filePath)];
    if (outDir) args.push(`-o${outDir}`);
    try {
        await execa(sevenZPath, args, {
            ...opts,
            stdio: 'inherit',
        });
    } catch (e) {
        console.error('run7z failed:', sevenZPath, args, e);
        return false;
    }
    return true;
}
