jest.mock('./utils', () => ({
    log: jest.fn(),
}));

import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { BIDSIGNORE_ENTRIES } from './preprocess.consts';
import {
    extractErrorBlocks,
    findBidsRoot,
    findFilesUnder,
    findSpecialCharPaths,
    gzipFile,
    intersection,
    readLines,
    runParallel,
    runRenameSpecialChars,
    updateBidsignore,
} from './preprocess.utils';
import { log } from './utils';

const mockedLog = log as jest.MockedFunction<typeof log>;

/** Creates a unique temp directory, runs the callback, then deletes the tree. */
function withTempDir(prefix: string, run: (root: string) => void | Promise<void>): void | Promise<void> {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), `ezbids-${prefix}-`));
    try {
        return run(root);
    } finally {
        fs.rmSync(root, { recursive: true, force: true });
    }
}

async function withTempDirAsync(prefix: string, run: (root: string) => Promise<void>): Promise<void> {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), `ezbids-${prefix}-`));
    try {
        await run(root);
    } finally {
        fs.rmSync(root, { recursive: true, force: true });
    }
}

describe('preprocess.utils', () => {
    beforeEach(() => {
        mockedLog.mockClear();
    });

    describe('intersection', () => {
        it('returns only values that appear in both arrays, in first-array order', () => {
            expect(intersection(['a', 'b', 'c', 'b'], ['c', 'b', 'a'])).toEqual(['a', 'b', 'c', 'b']);
        });

        it('returns empty array when first array is empty', () => {
            expect(intersection([], ['a', 'b'])).toEqual([]);
        });

        it('returns empty array when second array is empty', () => {
            expect(intersection(['a', 'b'], [])).toEqual([]);
        });

        it('returns empty array when there is no overlap', () => {
            expect(intersection(['x'], ['y'])).toEqual([]);
        });

        it('deduplicates via Set on second list only (duplicates in first preserved)', () => {
            expect(intersection(['a', 'a'], ['a'])).toEqual(['a', 'a']);
        });
    });

    describe('extractErrorBlocks', () => {
        it('returns empty string when there are no matching lines', () => {
            expect(extractErrorBlocks('all quiet\nnothing here')).toBe('');
        });

        it('matches "Error" case-insensitively', () => {
            expect(extractErrorBlocks('prefix ERROR suffix')).toContain('prefix ERROR suffix');
            expect(extractErrorBlocks('lowercase error in line')).toContain('lowercase error in line');
        });

        it('matches whenever "Error" appears as a substring (regex is not word-boundary aware)', () => {
            expect(extractErrorBlocks('Terror in the deep')).toContain('Terror in the deep');
        });

        it('appends a blank line after each matched line (join does not add an extra trailing blank)', () => {
            const out = extractErrorBlocks('quiet\nError: first\nquiet\nError: second');
            expect(out).toBe('Error: first\n\nError: second\n');
        });

        it('handles empty input', () => {
            expect(extractErrorBlocks('')).toBe('');
        });

        it('handles only newlines', () => {
            expect(extractErrorBlocks('\n\n\r\n')).toBe('');
        });

        it('splits on classic Mac CR only', () => {
            expect(extractErrorBlocks('ok\rError: mac')).toContain('Error: mac');
        });

        it('collects multiple non-consecutive error lines (substring must match /Error/i)', () => {
            const out = extractErrorBlocks('a\nError: one\nb\nc\nERROR two');
            expect(out).toContain('Error: one');
            expect(out).toContain('ERROR two');
        });
    });

    describe('readLines', () => {
        it('returns empty array when file is missing', () => {
            expect(readLines(path.join(os.tmpdir(), `ezbids-missing-${Date.now()}.txt`))).toEqual([]);
        });

        it('trims each line and drops blank lines after trim', () => {
            withTempDir('readlines', (root) => {
                const file = path.join(root, 'lines.txt');
                fs.writeFileSync(file, '  a  \n\nb\r\nc\n   \nd', 'utf8');
                expect(readLines(file)).toEqual(['a', 'b', 'c', 'd']);
            });
        });

        it('returns empty array for an empty file', () => {
            withTempDir('readlines-empty', (root) => {
                const file = path.join(root, 'empty.txt');
                fs.writeFileSync(file, '', 'utf8');
                expect(readLines(file)).toEqual([]);
            });
        });

        it('treats a file of only whitespace as empty', () => {
            withTempDir('readlines-ws', (root) => {
                const file = path.join(root, 'ws.txt');
                fs.writeFileSync(file, ' \n\t\n  ', 'utf8');
                expect(readLines(file)).toEqual([]);
            });
        });
    });

    describe('findSpecialCharPaths', () => {
        it('collects each special character class: space, @, ^, (, )', () => {
            withTempDir('specchars', (root) => {
                fs.mkdirSync(path.join(root, 'a b'));
                fs.writeFileSync(path.join(root, 'at@at.txt'), '');
                fs.writeFileSync(path.join(root, 'caret^here.txt'), '');
                fs.mkdirSync(path.join(root, 'paren(open'));
                fs.mkdirSync(path.join(root, 'paren)close'));
                const found = findSpecialCharPaths(root)
                    .map((p) => path.basename(p))
                    .sort();
                expect(found).toEqual(['a b', 'at@at.txt', 'caret^here.txt', 'paren(open', 'paren)close'].sort());
            });
        });

        it('does not list paths whose basenames have no special characters', () => {
            withTempDir('specchars-clean', (root) => {
                fs.mkdirSync(path.join(root, 'clean'));
                fs.writeFileSync(path.join(root, 'ok-file.txt'), '');
                expect(findSpecialCharPaths(root)).toEqual([]);
            });
        });

        it('orders deeper paths before their parent so renames run leaf-first (reverse of ascending path sort)', () => {
            withTempDir('specchars-sort', (root) => {
                const parent = path.join(root, 'a b');
                fs.mkdirSync(parent, { recursive: true });
                const inner = path.join(parent, 'inner c.txt');
                fs.writeFileSync(inner, '');
                const found = findSpecialCharPaths(root);
                expect(found).toEqual([parent, inner].sort().reverse());
            });
        });
    });

    describe('findFilesUnder', () => {
        it('returns posix-style relative paths for files matching predicate (path.posix.join drops redundant ./ )', () => {
            withTempDir('ffu', (root) => {
                fs.mkdirSync(path.join(root, 'sub'));
                fs.writeFileSync(path.join(root, 'a.txt'), '');
                fs.writeFileSync(path.join(root, 'sub', 'b.txt'), '');
                fs.writeFileSync(path.join(root, 'sub', 'c.nii'), '');
                const txt = findFilesUnder(root, 5, (name) => name.endsWith('.txt')).sort();
                expect(txt).toEqual(['a.txt', 'sub/b.txt'].sort());
            });
        });

        it('respects maxDepth: does not descend when child depth would exceed maxDepth', () => {
            withTempDir('ffu-depth', (root) => {
                fs.mkdirSync(path.join(root, 'l1', 'l2'), { recursive: true });
                fs.writeFileSync(path.join(root, 'root.txt'), '');
                fs.writeFileSync(path.join(root, 'l1', 'one.txt'), '');
                fs.writeFileSync(path.join(root, 'l1', 'l2', 'two.txt'), '');
                const atDepth0 = findFilesUnder(root, 0, (n) => n.endsWith('.txt')).sort();
                expect(atDepth0).toEqual(['root.txt']);
                const atDepth1 = findFilesUnder(root, 1, (n) => n.endsWith('.txt')).sort();
                expect(atDepth1).toEqual(['l1/one.txt', 'root.txt'].sort());
            });
        });

        it('returns empty array when no files match', () => {
            withTempDir('ffu-none', (root) => {
                fs.writeFileSync(path.join(root, 'x.bin'), '');
                expect(findFilesUnder(root, 3, (n) => n.endsWith('.missing'))).toEqual([]);
            });
        });
    });

    describe('runParallel', () => {
        it('runs runOne for every item and resolves when all complete', async () => {
            const order: number[] = [];
            await runParallel([1, 2, 3], async (n) => {
                order.push(n);
                return { status: 0, stderr: '' };
            });
            expect(order.sort()).toEqual([1, 2, 3]);
        });

        it('appends stderr to file when appendStderrToFilePath is set and stderr is non-empty', async () => {
            await withTempDirAsync('rp-stderr', async (root) => {
                const errFile = path.join(root, 'errs.log');
                await runParallel(['a', 'b'], async () => ({ status: 0, stderr: 'x' }), errFile, 10);
                const content = fs.readFileSync(errFile, 'utf8');
                expect(content).toBe('xx');
            });
        });

        it('does not write stderr file when stderr is empty', async () => {
            await withTempDirAsync('rp-no-stderr', async (root) => {
                const errFile = path.join(root, 'errs.log');
                await runParallel([1], async () => ({ status: 0, stderr: '' }), errFile);
                expect(fs.existsSync(errFile)).toBe(false);
            });
        });

        it('does not append when appendStderrToFilePath is omitted', async () => {
            await runParallel([1], async () => ({ status: 0, stderr: 'should not be written' }));
            // no throw; nothing to assert on disk
        });

        it('handles empty items array', async () => {
            await expect(runParallel([], async () => ({ status: 0, stderr: '' }))).resolves.toBeUndefined();
        });

        it('rejects if any runOne promise rejects', async () => {
            await expect(
                runParallel([1, 2], async (n) => {
                    if (n === 2) throw new Error('boom');
                    return { status: 0, stderr: '' };
                })
            ).rejects.toThrow('boom');
        });

        it('accepts an explicit maxParallel argument', async () => {
            const calls: number[] = [];
            await runParallel(
                [1, 2, 3],
                async (n) => {
                    calls.push(n);
                    return { status: 0, stderr: '' };
                },
                undefined,
                2
            );
            expect(calls.sort()).toEqual([1, 2, 3]);
        });
    });

    describe('gzipFile', () => {
        it('creates .gz next to source and removes the original on success', async () => {
            await withTempDirAsync('gzip-ok', async (root) => {
                const src = path.join(root, 'data.txt');
                fs.writeFileSync(src, 'hello gzip', 'utf8');
                await gzipFile(src);
                const gz = src + '.gz';
                expect(fs.existsSync(src)).toBe(false);
                expect(fs.existsSync(gz)).toBe(true);
                expect(fs.readFileSync(gz).length).toBeGreaterThan(0);
            });
        });

        it('accepts an empty source file', async () => {
            await withTempDirAsync('gzip-empty', async (root) => {
                const src = path.join(root, 'empty.dat');
                fs.writeFileSync(src, '', 'utf8');
                await gzipFile(src);
                expect(fs.existsSync(src)).toBe(false);
                expect(fs.existsSync(src + '.gz')).toBe(true);
            });
        });

        it('rejects and removes partial .gz when the source cannot be read', async () => {
            await withTempDirAsync('gzip-fail', async (root) => {
                const src = path.join(root, 'nope.txt');
                const gz = src + '.gz';
                await expect(gzipFile(src)).rejects.toBeDefined();
                expect(fs.existsSync(gz)).toBe(false);
            });
        });
    });

    describe('findBidsRoot', () => {
        it('returns the directory containing dataset_description.json when found within max depth', () => {
            withTempDir('bids-found', (root) => {
                const bids = path.join(root, 'mybids');
                fs.mkdirSync(bids);
                fs.writeFileSync(path.join(bids, 'dataset_description.json'), '{}');
                expect(findBidsRoot(root)).toBe(bids);
            });
        });

        it('returns rootPath when dataset_description.json sits in the root directory', () => {
            withTempDir('bids-rootfile', (root) => {
                fs.writeFileSync(path.join(root, 'dataset_description.json'), '{}');
                expect(findBidsRoot(root)).toBe(root);
            });
        });

        it('returns rootPath when dataset_description.json is absent', () => {
            withTempDir('bids-missing', (root) => {
                fs.writeFileSync(path.join(root, 'other.json'), '{}');
                expect(findBidsRoot(root)).toBe(root);
            });
        });

        it('does not find dataset_description.json deeper than max depth (5)', () => {
            withTempDir('bids-deep', (root) => {
                const deep = path.join(root, 'l1', 'l2', 'l3', 'l4', 'l5', 'l6');
                fs.mkdirSync(deep, { recursive: true });
                fs.writeFileSync(path.join(deep, 'dataset_description.json'), '{}');
                expect(findBidsRoot(root)).toBe(root);
            });
        });
    });

    describe('runRenameSpecialChars', () => {
        it('renames basenames that contain special characters and logs each rename', () => {
            withTempDir('rename', (root) => {
                const badDir = path.join(root, 'a b');
                fs.mkdirSync(badDir);
                const badFile = path.join(badDir, 'f@x.txt');
                fs.writeFileSync(badFile, 'x');
                runRenameSpecialChars(root);
                const newDir = path.join(root, 'a_b');
                const newFile = path.join(newDir, 'f_x.txt');
                expect(fs.existsSync(badDir)).toBe(false);
                expect(fs.existsSync(badFile)).toBe(false);
                expect(fs.existsSync(newFile)).toBe(true);
                expect(mockedLog).toHaveBeenCalledWith(expect.stringContaining('Renaming'));
            });
        });

        it('replaces every matched character in the basename with a single underscore', () => {
            withTempDir('rename-multi', (root) => {
                const name = 'a b@c^d(e)f.txt';
                const src = path.join(root, name);
                fs.writeFileSync(src, '');
                runRenameSpecialChars(root);
                const expectedName = 'a_b_c_d_e_f.txt';
                expect(fs.existsSync(path.join(root, expectedName))).toBe(true);
                expect(fs.existsSync(src)).toBe(false);
            });
        });

        it('when nothing needs renaming, logs the intro only and performs no Renaming logs', () => {
            withTempDir('rename-clean', (root) => {
                fs.writeFileSync(path.join(root, 'clean.txt'), '');
                runRenameSpecialChars(root);
                expect(mockedLog).toHaveBeenCalledWith(expect.stringContaining('replace file paths'));
                expect(mockedLog.mock.calls.filter((c) => String(c[0]).includes('Renaming'))).toHaveLength(0);
            });
        });
    });

    describe('updateBidsignore', () => {
        it('creates .bidsignore with all BIDSIGNORE_ENTRIES when file did not exist', () => {
            withTempDir('bidsignore-new', (root) => {
                updateBidsignore(root);
                const content = fs.readFileSync(path.join(root, '.bidsignore'), 'utf8');
                const lines = content.trimEnd().split('\n');
                for (const entry of BIDSIGNORE_ENTRIES) {
                    expect(lines).toContain(entry);
                }
                expect(content.endsWith('\n')).toBe(true);
            });
        });

        it('merges new entries without removing existing unrelated lines', () => {
            withTempDir('bidsignore-merge', (root) => {
                fs.writeFileSync(path.join(root, '.bidsignore'), 'custom_rule/**\n', 'utf8');
                updateBidsignore(root);
                const lines = fs.readFileSync(path.join(root, '.bidsignore'), 'utf8').split('\n').filter(Boolean);
                expect(lines).toContain('custom_rule/**');
                expect(lines).toContain(BIDSIGNORE_ENTRIES[0]);
            });
        });

        it('deduplicates when file already contains a BIDSIGNORE_ENTRIES line', () => {
            withTempDir('bidsignore-dedupe', (root) => {
                const dup = BIDSIGNORE_ENTRIES[0];
                fs.writeFileSync(path.join(root, '.bidsignore'), `${dup}\n`, 'utf8');
                updateBidsignore(root);
                const lines = fs
                    .readFileSync(path.join(root, '.bidsignore'), 'utf8')
                    .split('\n')
                    .filter((l) => l === dup);
                expect(lines.length).toBe(1);
            });
        });

        it('normalizes CRLF in existing file into single-line set semantics', () => {
            withTempDir('bidsignore-crlf', (root) => {
                fs.writeFileSync(path.join(root, '.bidsignore'), 'keep_me\r\n', 'utf8');
                updateBidsignore(root);
                const text = fs.readFileSync(path.join(root, '.bidsignore'), 'utf8');
                expect(text.split('\n').filter(Boolean)).toContain('keep_me');
            });
        });
    });
});
