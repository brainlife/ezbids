import { execa, Options } from 'execa';
import * as fs from 'fs';
import * as path from 'path';
import { getBinPath } from './utils';

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
    const sevenZPath = path.join(getBinPath('7z'), `7z-${process.env.EZBIDS_PLATFORM}-${process.env.EZBIDS_ARCH}`);
    const args = ['x', path.basename(filePath)];
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
