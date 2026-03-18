#!/usr/bin/env node
/**
 * Recursively expand archives under root.
 * Uses 7z for all formats: .tar/.tar.gz/.tgz, .gz, .bz2, .7z, .zip, .rar, .zst.
 * Repeats until no archives remain.
 */
import * as fs from 'fs';
import * as path from 'path';
import { allFilesUnder, extract7z, rm } from './expand.utils';

const root = process.argv[2];
if (!root || !fs.existsSync(root)) {
    console.error('usage: node expand.js <root-dir>');
    process.exit(1);
}

function onePass(rootPath: string): boolean {
    const files = allFilesUnder(rootPath);
    let expanded = false;
    let expandCounter = 1;

    const archives: string[] = []; // .tar.gz, .tgz, .tar*, .7z, .zip, .rar → extract to subdir
    const singleCompressed: string[] = []; // .gz, .bz2, .zst → extract in place

    files.forEach((file) => {
        if (
            file.endsWith('.tar.gz') ||
            file.endsWith('.tgz') ||
            file.includes('.tar') ||
            file.endsWith('.7z') ||
            file.endsWith('.zip') ||
            file.endsWith('.rar')
        ) {
            archives.push(file);
        } else if (file.endsWith('.gz') && !file.endsWith('.nii.gz')) {
            singleCompressed.push(file);
        } else if (file.endsWith('.bz2') || file.endsWith('.zst')) {
            singleCompressed.push(file);
        }
    });

    for (const file of archives) {
        if (!fs.existsSync(file)) continue;
        const dir = path.dirname(file);
        const outDirName = String(expandCounter);
        fs.mkdirSync(path.join(dir, outDirName), { recursive: true });
        if (extract7z(file, dir, outDirName)) {
            rm(file);
            expanded = true;
            expandCounter++;
        }
    }

    for (const file of singleCompressed) {
        if (!fs.existsSync(file)) continue;
        const dir = path.dirname(file);
        if (extract7z(file, dir)) {
            rm(file);
            expanded = true;
        }
    }

    return expanded;
}

function main(): void {
    const rootPath = path.resolve(root);
    // eslint-disable-next-line no-console -- CLI script
    console.log('expanding archives in', rootPath);

    let expanded: boolean;
    do {
        expanded = onePass(rootPath);
    } while (expanded);
    // eslint-disable-next-line no-console -- CLI script
    console.log('no more archives to expand .. done');
}

main();
