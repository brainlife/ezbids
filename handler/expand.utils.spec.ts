jest.mock('execa', () => ({
    execa: jest.fn(),
}));

jest.mock('./utils', () => ({
    getBinPath: jest.fn(),
}));

import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { execa } from 'execa';
import { allFilesUnder, rm, run7z, walkDir } from './expand.utils';
import { getBinPath } from './utils';

const mockedExeca = execa as jest.MockedFunction<typeof execa>;
const mockedGetBinPath = getBinPath as jest.MockedFunction<typeof getBinPath>;

function withTempDir(prefix: string, run: (root: string) => void): void {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), `ezbids-${prefix}-`));
    try {
        run(root);
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

describe('expand.utils', () => {
    const prevPlatform = process.env.EZBIDS_PLATFORM;
    const prevArch = process.env.EZBIDS_ARCH;

    beforeEach(() => {
        mockedExeca.mockReset();
        mockedGetBinPath.mockReset();
        process.env.EZBIDS_PLATFORM = 'linux';
        process.env.EZBIDS_ARCH = 'amd64';
    });

    afterEach(() => {
        process.env.EZBIDS_PLATFORM = prevPlatform;
        process.env.EZBIDS_ARCH = prevArch;
    });

    describe('walkDir', () => {
        it('recursively collects only files, not directories', () => {
            withTempDir('walk', (root) => {
                fs.mkdirSync(path.join(root, 'a', 'b'), { recursive: true });
                fs.writeFileSync(path.join(root, 'root.txt'), '');
                fs.writeFileSync(path.join(root, 'a', 'one.txt'), '');
                fs.writeFileSync(path.join(root, 'a', 'b', 'two.txt'), '');
                const files: string[] = [];
                walkDir(root, files);
                expect(files.sort()).toEqual(
                    [
                        path.join(root, 'root.txt'),
                        path.join(root, 'a', 'one.txt'),
                        path.join(root, 'a', 'b', 'two.txt'),
                    ].sort()
                );
            });
        });

        it('mutates the passed-in array', () => {
            withTempDir('walk-mutate', (root) => {
                fs.writeFileSync(path.join(root, 'x.txt'), '');
                const acc: string[] = [];
                walkDir(root, acc);
                expect(acc.length).toBe(1);
            });
        });
    });

    describe('allFilesUnder', () => {
        it('returns empty array when the tree has no files', () => {
            withTempDir('all-empty', (root) => {
                fs.mkdirSync(path.join(root, 'empty-dir'));
                expect(allFilesUnder(root)).toEqual([]);
            });
        });

        it('returns all file paths under root', () => {
            withTempDir('all-files', (root) => {
                fs.mkdirSync(path.join(root, 'sub'));
                fs.writeFileSync(path.join(root, 'a.txt'), '');
                fs.writeFileSync(path.join(root, 'sub', 'b.txt'), '');
                expect(allFilesUnder(root).sort()).toEqual(
                    [path.join(root, 'a.txt'), path.join(root, 'sub', 'b.txt')].sort()
                );
            });
        });
    });

    describe('rm', () => {
        it('removes an existing file', () => {
            withTempDir('rm-ok', (root) => {
                const f = path.join(root, 't.txt');
                fs.writeFileSync(f, '1');
                rm(f);
                expect(fs.existsSync(f)).toBe(false);
            });
        });

        it('logs and does not throw when the file is missing', () => {
            const errSpy = jest.spyOn(console, 'error').mockImplementation(jest.fn());
            try {
                rm(path.join(os.tmpdir(), `ezbids-rm-missing-${Date.now()}.txt`));
                expect(errSpy).toHaveBeenCalledWith(
                    expect.stringContaining('rm failed:'),
                    expect.anything(),
                    expect.anything()
                );
            } finally {
                errSpy.mockRestore();
            }
        });
    });

    describe('run7z', () => {
        function setupSevenZipLayout(binRoot: string): { sevenZPath: string; archiveDir: string; archivePath: string } {
            const sevenDir = path.join(binRoot, '7z');
            fs.mkdirSync(sevenDir, { recursive: true });
            const sevenZPath = path.join(sevenDir, '7z-linux-amd64');
            fs.writeFileSync(sevenZPath, '');
            const archiveDir = path.join(binRoot, 'work');
            fs.mkdirSync(archiveDir, { recursive: true });
            const archivePath = path.join(archiveDir, 'data.zip');
            fs.writeFileSync(archivePath, '');
            mockedGetBinPath.mockImplementation((tool: string) => path.join(binRoot, tool));
            return { sevenZPath, archiveDir, archivePath };
        }

        it('invokes 7z with x, -y, archive basename, and merged opts; returns true on success', async () => {
            await withTempDirAsync('run7z-ok', async (root) => {
                const { sevenZPath, archiveDir, archivePath } = setupSevenZipLayout(root);
                mockedExeca.mockResolvedValue({} as Awaited<ReturnType<typeof execa>>);

                const ok = await run7z(archivePath, { cwd: archiveDir });

                expect(ok).toBe(true);
                expect(mockedExeca).toHaveBeenCalledTimes(1);
                expect(mockedExeca).toHaveBeenCalledWith(
                    sevenZPath,
                    ['x', '-y', 'data.zip'],
                    expect.objectContaining({ cwd: archiveDir, stdio: 'inherit' })
                );
            });
        });

        it('appends -o<outDir> when outDir is provided', async () => {
            await withTempDirAsync('run7z-out', async (root) => {
                const { archiveDir, archivePath } = setupSevenZipLayout(root);
                mockedExeca.mockResolvedValue({} as Awaited<ReturnType<typeof execa>>);
                const outAbs = path.join(root, 'extracted');

                await run7z(archivePath, { cwd: archiveDir }, outAbs);

                expect(mockedExeca.mock.calls[0][1]).toEqual(['x', '-y', 'data.zip', `-o${outAbs}`]);
            });
        });

        it('passes -tgzip for .gz (but not .tar.gz / .tgz)', async () => {
            await withTempDirAsync('run7z-gz', async (root) => {
                const { archiveDir } = setupSevenZipLayout(root);
                const plainGz = path.join(archiveDir, 'file.gz');
                fs.writeFileSync(plainGz, '');
                mockedExeca.mockResolvedValue({} as Awaited<ReturnType<typeof execa>>);

                await run7z(plainGz, { cwd: archiveDir });

                expect(mockedExeca.mock.calls[0][1]).toEqual(['x', '-y', '-tgzip', 'file.gz']);
            });
        });

        it('does not pass a type flag for .tar.gz or .tgz', async () => {
            await withTempDirAsync('run7z-targz', async (root) => {
                const { archiveDir } = setupSevenZipLayout(root);
                for (const name of ['bundle.tar.gz', 'short.tgz'] as const) {
                    mockedExeca.mockClear();
                    const p = path.join(archiveDir, name);
                    fs.writeFileSync(p, '');
                    mockedExeca.mockResolvedValue({} as Awaited<ReturnType<typeof execa>>);
                    await run7z(p, { cwd: archiveDir });
                    expect(mockedExeca.mock.calls[0][1]).toEqual(['x', '-y', name]);
                }
            });
        });

        it('passes -tbzip2 for .bz2 and -tzstd for .zst', async () => {
            await withTempDirAsync('run7z-types', async (root) => {
                const { archiveDir } = setupSevenZipLayout(root);
                const bz = path.join(archiveDir, 'x.bz2');
                fs.writeFileSync(bz, '');
                mockedExeca.mockResolvedValue({} as Awaited<ReturnType<typeof execa>>);
                await run7z(bz, { cwd: archiveDir });
                expect(mockedExeca.mock.calls[0][1]).toEqual(['x', '-y', '-tbzip2', 'x.bz2']);

                mockedExeca.mockClear();
                const zst = path.join(archiveDir, 'y.zst');
                fs.writeFileSync(zst, '');
                mockedExeca.mockResolvedValue({} as Awaited<ReturnType<typeof execa>>);
                await run7z(zst, { cwd: archiveDir });
                expect(mockedExeca.mock.calls[0][1]).toEqual(['x', '-y', '-tzstd', 'y.zst']);
            });
        });

        it('returns false and logs when execa rejects', async () => {
            const errSpy = jest.spyOn(console, 'error').mockImplementation(jest.fn());
            try {
                await withTempDirAsync('run7z-fail', async (root) => {
                    const { archiveDir, archivePath } = setupSevenZipLayout(root);
                    mockedExeca.mockRejectedValue(new Error('7z exited'));

                    const ok = await run7z(archivePath, { cwd: archiveDir });

                    expect(ok).toBe(false);
                    expect(errSpy).toHaveBeenCalledWith(
                        'run7z failed:',
                        expect.any(String),
                        ['x', '-y', 'data.zip'],
                        expect.any(Error)
                    );
                });
            } finally {
                errSpy.mockRestore();
            }
        });

        describe('Windows 7z.dll check', () => {
            it('throws before execa when EZBIDS_PLATFORM is windows and 7z.dll is missing', async () => {
                await withTempDirAsync('run7z-win-nodll', async (root) => {
                    process.env.EZBIDS_PLATFORM = 'windows';
                    process.env.EZBIDS_ARCH = 'amd64';
                    const sevenDir = path.join(root, '7z');
                    fs.mkdirSync(sevenDir, { recursive: true });
                    const sevenZPath = path.join(sevenDir, '7z-windows-amd64.exe');
                    fs.writeFileSync(sevenZPath, '');
                    mockedGetBinPath.mockImplementation((tool: string) => path.join(root, tool));

                    const archiveDir = path.join(root, 'work');
                    fs.mkdirSync(archiveDir, { recursive: true });
                    const archivePath = path.join(archiveDir, 'a.zip');
                    fs.writeFileSync(archivePath, '');

                    await expect(run7z(archivePath, { cwd: archiveDir })).rejects.toThrow(/7z\.dll/);
                    expect(mockedExeca).not.toHaveBeenCalled();
                });
            });

            it('runs execa when windows and 7z.dll exists beside the executable', async () => {
                await withTempDirAsync('run7z-win-dll', async (root) => {
                    process.env.EZBIDS_PLATFORM = 'windows';
                    process.env.EZBIDS_ARCH = 'amd64';
                    const sevenDir = path.join(root, '7z');
                    fs.mkdirSync(sevenDir, { recursive: true });
                    const sevenZPath = path.join(sevenDir, '7z-windows-amd64.exe');
                    fs.writeFileSync(sevenZPath, '');
                    fs.writeFileSync(path.join(sevenDir, '7z.dll'), '');
                    mockedGetBinPath.mockImplementation((tool: string) => path.join(root, tool));

                    const archiveDir = path.join(root, 'work');
                    fs.mkdirSync(archiveDir, { recursive: true });
                    const archivePath = path.join(archiveDir, 'a.zip');
                    fs.writeFileSync(archivePath, '');
                    mockedExeca.mockResolvedValue({} as Awaited<ReturnType<typeof execa>>);

                    const ok = await run7z(archivePath, { cwd: archiveDir });

                    expect(ok).toBe(true);
                    expect(mockedExeca).toHaveBeenCalled();
                });
            });
        });
    });
});
