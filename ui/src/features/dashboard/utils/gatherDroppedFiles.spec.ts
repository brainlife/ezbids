import { gatherDroppedFiles } from './gatherDroppedFiles';

/** Minimal DataTransferItemList shape used by gatherDroppedFiles (indexed + length). */
function asDataTransferItemList(
    items: Array<{ webkitGetAsEntry: () => FileSystemEntry | null }>
): DataTransferItemList {
    return items as unknown as DataTransferItemList;
}

function mockFileEntry(fullPath: string, file: File): FileSystemFileEntry {
    return {
        isFile: true,
        isDirectory: false,
        fullPath,
        file(success: (f: File) => void, _reject: (err: Error) => void) {
            queueMicrotask(() => success(file));
        },
    } as FileSystemFileEntry;
}

function createDirectoryReader(batches: FileSystemEntry[][]): FileSystemDirectoryReader {
    let call = 0;
    return {
        readEntries(successCallback: (entries: FileSystemEntry[]) => void, _errorCallback: (err: Error) => void) {
            const batch = call < batches.length ? batches[call]! : [];
            call += 1;
            queueMicrotask(() => successCallback(batch));
        },
    } as FileSystemDirectoryReader;
}

function mockDirectoryEntry(fullPath: string, reader: FileSystemDirectoryReader): FileSystemDirectoryEntry {
    return {
        isFile: false,
        isDirectory: true,
        fullPath,
        createReader: () => reader,
    } as FileSystemDirectoryEntry;
}

describe('gatherDroppedFiles', () => {
    it('returns [] for null, undefined, or zero-length items', async () => {
        await expect(gatherDroppedFiles(null)).resolves.toEqual([]);
        await expect(gatherDroppedFiles(undefined)).resolves.toEqual([]);
        await expect(gatherDroppedFiles({ length: 0 } as DataTransferItemList)).resolves.toEqual([]);
    });

    it('returns [] when every item has no webkit entry', async () => {
        const items = asDataTransferItemList([{ webkitGetAsEntry: () => null }]);
        await expect(gatherDroppedFiles(items)).resolves.toEqual([]);
    });

    it('reads a single file, assigns path from fullPath (leading slash stripped)', async () => {
        const blob = new File(['x'], 'a.dcm');
        const entry = mockFileEntry('/dataset/sub-01/a.dcm', blob);
        const items = asDataTransferItemList([{ webkitGetAsEntry: () => entry }]);

        const out = await gatherDroppedFiles(items);

        expect(out).toHaveLength(1);
        expect(out[0]).toBe(blob);
        expect((out[0] as File & { path?: string }).path).toBe('dataset/sub-01/a.dcm');
    });

    it('walks a directory whose entries arrive in one readEntries batch', async () => {
        const f1 = new File(['1'], '1.dcm');
        const f2 = new File(['2'], '2.dcm');
        const reader = createDirectoryReader([
            [mockFileEntry('/root/1.dcm', f1), mockFileEntry('/root/2.dcm', f2)],
            [],
        ]);
        const dir = mockDirectoryEntry('/root', reader);
        const items = asDataTransferItemList([{ webkitGetAsEntry: () => dir }]);

        const out = await gatherDroppedFiles(items);

        expect(out).toHaveLength(2);
        const paths = out.map((f) => (f as File & { path?: string }).path).sort();
        expect(paths).toEqual(['root/1.dcm', 'root/2.dcm']);
    });

    it('drains readEntries until an empty batch (Chrome-style chunking)', async () => {
        const f1 = new File(['a'], 'a.dcm');
        const f2 = new File(['b'], 'b.dcm');
        const reader = createDirectoryReader([[mockFileEntry('/d/a.dcm', f1)], [mockFileEntry('/d/b.dcm', f2)], []]);
        const dir = mockDirectoryEntry('/d', reader);
        const items = asDataTransferItemList([{ webkitGetAsEntry: () => dir }]);

        const out = await gatherDroppedFiles(items);

        expect(out.map((f) => (f as File & { path?: string }).path).sort()).toEqual(['d/a.dcm', 'd/b.dcm']);
    });

    it('recurses into nested directories', async () => {
        const leaf = new File(['z'], 'z.dcm');
        const innerReader = createDirectoryReader([[mockFileEntry('/outer/inner/z.dcm', leaf)], []]);
        const innerDir = mockDirectoryEntry('/outer/inner', innerReader);
        const outerReader = createDirectoryReader([[innerDir], []]);
        const outerDir = mockDirectoryEntry('/outer', outerReader);
        const items = asDataTransferItemList([{ webkitGetAsEntry: () => outerDir }]);

        const out = await gatherDroppedFiles(items);

        expect(out).toHaveLength(1);
        expect((out[0] as File & { path?: string }).path).toBe('outer/inner/z.dcm');
    });

    it('omits files when fileEntry.file rejects', async () => {
        const badEntry = {
            isFile: true,
            isDirectory: false,
            fullPath: '/bad/x.dcm',
            file(_success: (f: File) => void, reject: (err: Error) => void) {
                queueMicrotask(() => reject(new Error('read failed')));
            },
        } as FileSystemFileEntry;

        const errSpy = jest.spyOn(console, 'error').mockImplementation(() => {});

        const items = asDataTransferItemList([{ webkitGetAsEntry: () => badEntry }]);
        await expect(gatherDroppedFiles(items)).resolves.toEqual([]);

        errSpy.mockRestore();
    });
});
