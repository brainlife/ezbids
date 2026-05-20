import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { getDatasetName, tree } from './bids.utils';

function withTempDir(prefix: string, run: (root: string) => void): void {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), `ezbids-${prefix}-`));
    try {
        run(root);
    } finally {
        fs.rmSync(root, { recursive: true, force: true });
    }
}

describe('bids.utils', () => {
    describe('tree', () => {
        it('prints the root basename then nothing when the directory is empty', () => {
            withTempDir('tree-empty', (root) => {
                const name = path.basename(root);
                expect(tree(root)).toBe(`${name}\n`);
            });
        });

        it('lists directories before files, then names case-insensitively (en)', () => {
            withTempDir('tree-sort', (root) => {
                fs.mkdirSync(path.join(root, 'B_folder'));
                fs.writeFileSync(path.join(root, 'a.txt'), '');
                fs.writeFileSync(path.join(root, 'Z.txt'), '');
                const out = tree(root);
                const base = path.basename(root);
                expect(out).toBe(`${base}\n` + '├── B_folder\n' + '├── a.txt\n' + '└── Z.txt\n');
            });
        });

        it('uses ├── for non-last siblings and └── for the last entry', () => {
            withTempDir('tree-connectors', (root) => {
                fs.writeFileSync(path.join(root, 'first.txt'), '');
                fs.writeFileSync(path.join(root, 'last.txt'), '');
                const base = path.basename(root);
                expect(tree(root)).toBe(`${base}\n` + '├── first.txt\n' + '└── last.txt\n');
            });
        });

        it('indents nested directories with tree branches', () => {
            withTempDir('tree-nested', (root) => {
                fs.mkdirSync(path.join(root, 'parent', 'child'), { recursive: true });
                fs.writeFileSync(path.join(root, 'parent', 'child', 'leaf.txt'), '');
                const base = path.basename(root);
                expect(tree(root)).toBe(`${base}\n` + '└── parent\n' + '    └── child\n' + '        └── leaf.txt\n');
            });
        });

        it('with maxDepth > 0, stops descending when depth reaches maxDepth (no deeper files listed)', () => {
            withTempDir('tree-depth', (root) => {
                fs.mkdirSync(path.join(root, 'outer', 'inner'), { recursive: true });
                fs.writeFileSync(path.join(root, 'outer', 'inner', 'deep.txt'), '');
                const base = path.basename(root);
                const out = tree(root, 2);
                expect(out).toBe(`${base}\n` + '└── outer\n' + '    └── inner\n');
                expect(out).not.toContain('deep.txt');
            });
        });

        it('with maxDepth 0, descends without an artificial depth cap', () => {
            withTempDir('tree-unlimited', (root) => {
                fs.mkdirSync(path.join(root, 'd1', 'd2', 'd3'), { recursive: true });
                fs.writeFileSync(path.join(root, 'd1', 'd2', 'd3', 'f.txt'), '');
                const out = tree(root, 0);
                expect(out).toContain('d3');
                expect(out).toContain('f.txt');
            });
        });

        it('when readdir fails (e.g. missing subpath), stops that branch without throwing', () => {
            const missing = path.join(os.tmpdir(), `ezbids-tree-missing-${Date.now()}`);
            const name = path.basename(path.resolve(missing));
            expect(tree(missing)).toBe(`${name}\n`);
        });
    });

    describe('getDatasetName', () => {
        it('returns datasetDescription.Name from finalized.json', () => {
            withTempDir('gdn-ok', (root) => {
                fs.writeFileSync(
                    path.join(root, 'finalized.json'),
                    JSON.stringify({ datasetDescription: { Name: 'My Study' } }),
                    'utf8'
                );
                expect(getDatasetName(root)).toBe('My Study');
            });
        });

        it('throws when Name is missing', () => {
            withTempDir('gdn-no-name', (root) => {
                fs.writeFileSync(path.join(root, 'finalized.json'), JSON.stringify({ datasetDescription: {} }), 'utf8');
                expect(() => getDatasetName(root)).toThrow('datasetDescription.Name not found');
            });
        });

        it('throws when Name is not a string', () => {
            withTempDir('gdn-bad-type', (root) => {
                fs.writeFileSync(
                    path.join(root, 'finalized.json'),
                    JSON.stringify({ datasetDescription: { Name: 42 } }),
                    'utf8'
                );
                expect(() => getDatasetName(root)).toThrow('datasetDescription.Name not found');
            });
        });

        it('throws when finalized.json is not valid JSON', () => {
            withTempDir('gdn-bad-json', (root) => {
                fs.writeFileSync(path.join(root, 'finalized.json'), '{not json', 'utf8');
                expect(() => getDatasetName(root)).toThrow(SyntaxError);
            });
        });

        it('logs and calls process.exit(1) when finalized.json is missing', () => {
            const exitSpy = jest.spyOn(process, 'exit').mockImplementation(((code?: string | number | null) => {
                throw new Error(`exit:${code}`);
            }) as (code?: string | number | null | undefined) => never);
            const errSpy = jest.spyOn(console, 'error').mockImplementation(jest.fn());
            try {
                const ghost = path.join(os.tmpdir(), `ezbids-finalized-missing-${Date.now()}`);
                expect(() => getDatasetName(ghost)).toThrow('exit:1');
                expect(errSpy).toHaveBeenCalledWith(expect.stringContaining('finalized.json not found'));
            } finally {
                exitSpy.mockRestore();
                errSpy.mockRestore();
            }
        });
    });
});
