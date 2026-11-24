async function readEntriesPromise(directoryReader: FileSystemDirectoryReader): Promise<FileSystemEntry[]> {
    try {
        return await new Promise((resolve, reject) => {
            directoryReader.readEntries(resolve, reject);
        });
    } catch (err) {
        console.error(err);
        return [];
    }
}

async function readAllDirectoryEntries(directoryReader: FileSystemDirectoryReader): Promise<FileSystemEntry[]> {
    const entries: FileSystemEntry[] = [];
    let readEntries = await readEntriesPromise(directoryReader);
    while (readEntries.length > 0) {
        entries.push(...readEntries);
        readEntries = await readEntriesPromise(directoryReader);
    }
    return entries;
}

async function getFile(fileEntry: FileSystemFileEntry): Promise<File | undefined> {
    try {
        return await new Promise((resolve, reject) => fileEntry.file(resolve, reject));
    } catch (err) {
        console.error(err);
        return undefined;
    }
}

/**
 * Recursively read files from a DataTransferItemList (directory drop).
 * Matches the behavior previously embedded in Upload.vue.
 */
export async function gatherDroppedFiles(items: DataTransferItemList | undefined | null): Promise<File[]> {
    const files: File[] = [];
    if (!items?.length) return files;

    const queue: FileSystemEntry[] = [];
    for (let i = 0; i < items.length; i++) {
        const entry = items[i].webkitGetAsEntry();
        if (entry) queue.push(entry);
    }

    while (queue.length > 0) {
        const entry = queue.shift();
        if (!entry) continue;
        if (entry.isFile) {
            const file = await getFile(entry as FileSystemFileEntry);
            if (file) {
                // @ts-expect-error path used by upload API
                file.path = entry.fullPath.substring(1);
                files.push(file);
            }
        } else if (entry.isDirectory) {
            queue.push(...(await readAllDirectoryEntries((entry as FileSystemDirectoryEntry).createReader())));
        }
    }

    return files;
}
