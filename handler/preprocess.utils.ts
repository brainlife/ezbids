import * as fs from 'fs';
import pLimit from 'p-limit';
import * as path from 'path';
import { BIDSIGNORE_ENTRIES, MAX_PARALLEL } from './preprocess.consts';
import { pipeline } from 'stream/promises';
import * as zlib from 'zlib';
import { log } from './utils';

/** Find paths (files or dirs) under root whose basename contains space, @, ^, (, ). */
export function findSpecialCharPaths(rootPath: string): string[] {
    const out: string[] = [];
    const re = /[ @^()]/;
    function visit(dir: string): void {
        const entries = fs.readdirSync(dir, { withFileTypes: true });
        for (const e of entries) {
            const full = path.join(dir, e.name);
            if (re.test(e.name)) {
                out.push(full);
            }
            if (e.isDirectory()) {
                visit(full);
            }
        }
    }
    visit(rootPath);
    return out.sort().reverse(); // depth-first, rename deep first so parents get renamed last
}

export function findFilesUnder(rootPath: string, maxDepth: number, predicate: (name: string) => boolean): string[] {
    const out: string[] = [];
    function visit(dir: string, depth: number): void {
        if (depth > maxDepth) return;
        const entries = fs.readdirSync(dir, { withFileTypes: true });
        for (const e of entries) {
            const full = path.join(dir, e.name);
            const rel = path.relative(rootPath, full);
            if (e.isFile() && predicate(e.name)) {
                out.push(`./${rel}`);
            }
            if (e.isDirectory()) {
                visit(full, depth + 1);
            }
        }
    }
    visit(rootPath, 0);
    return out;
}

export function readLines(filePath: string): string[] {
    if (!fs.existsSync(filePath)) return [];
    return fs
        .readFileSync(filePath, 'utf8')
        .split(/\r?\n|\r/)
        .map((s) => s.trim())
        .filter(Boolean);
}

export function extractErrorBlocks(content: string): string {
    const lines = content.split(/\r?\n|\r/);
    const out: string[] = [];
    for (const line of lines) {
        if (/Error/i.test(line)) {
            out.push(line);
            out.push('');
        }
    }
    return out.join('\n');
}

export async function runParallel(
    items: string[],
    runOne: (item: string) => Promise<{ status: number; stderr: string }>,
    appendStderrToFilePath?: string
): Promise<void> {
    const limit = pLimit(MAX_PARALLEL);
    await Promise.all(
        items.map((item) =>
            limit(async () => {
                const r = await runOne(item);
                if (r.stderr && appendStderrToFilePath) {
                    fs.appendFileSync(appendStderrToFilePath, r.stderr);
                }
            })
        )
    );
}

export function intersection(a: string[], b: string[]): string[] {
    const setB = new Set(b);
    return a.filter((x) => setB.has(x));
}

/** Compress a file with gzip and remove the original (file.nii -> file.nii.gz). Rejects on error. */
export async function gzipFile(srcPath: string): Promise<void> {
    const destPath = srcPath + '.gz';
    try {
        await pipeline(fs.createReadStream(srcPath), zlib.createGzip(), fs.createWriteStream(destPath));
        fs.unlinkSync(srcPath);
    } catch (err) {
        if (fs.existsSync(destPath)) {
            try {
                fs.unlinkSync(destPath);
            } catch {
                // ignore cleanup failure
            }
        }
        throw err;
    }
}

/** BFS: find first file matching fileName at shallowest depth (up to maxDepth). */
function findFileMaxDepthBFS(rootDir: string, fileName: string, maxDepth: number): string | null {
    const queue: { path: string; depth: number }[] = [{ path: rootDir, depth: 0 }];
    while (queue.length > 0) {
        const { path: dir, depth } = queue.shift()!;
        const entries = fs.readdirSync(dir, { withFileTypes: true });
        for (const e of entries) {
            const full = path.join(dir, e.name);
            if (e.isFile() && e.name === fileName) {
                return full;
            }
            if (e.isDirectory() && depth < maxDepth) {
                queue.push({ path: full, depth: depth + 1 });
            }
        }
    }
    return null;
}

/** Find dataset_description.json under root, up to maxDepth. Returns directory containing it or root. */
export function findBidsRoot(rootPath: string): string | null {
    const found = findFileMaxDepthBFS(rootPath, 'dataset_description.json', 5);
    return found ? path.dirname(found) : rootPath;
}

export function runRenameSpecialChars(root: string): void {
    log('replace file paths that contain space, quotation, or [@^()] characters');
    const paths = findSpecialCharPaths(root);
    for (const p of paths) {
        if (fs.existsSync(p)) {
            const dir = path.dirname(p);
            const base = path.basename(p);
            const newBase = base.replace(/[ @^()]/g, '_');
            const newPath = path.join(dir, newBase);
            if (p !== newPath) {
                log(`Renaming '${p}' to '${newPath}'`);
                fs.renameSync(p, newPath);
            }
        }
    }
}

export function updateBidsignore(bidsRoot: string): void {
    const file = path.join(bidsRoot, '.bidsignore');
    let existing = '';
    if (fs.existsSync(file)) {
        existing = fs.readFileSync(file, 'utf8');
    }
    const lines = new Set(existing.split(/\r?\n|\r/).filter(Boolean));
    for (const entry of BIDSIGNORE_ENTRIES) {
        lines.add(entry);
    }
    fs.writeFileSync(file, [...lines].join('\n') + '\n');
}
