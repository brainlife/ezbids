import * as fs from 'fs';
import * as path from 'path';

/**
 * Build a tree-style listing of a directory (like the Unix `tree` command).
 * Uses only Node built-ins; works on all platforms.
 * @param dirPath - Directory to list (absolute or relative).
 * @param maxDepth - Maximum depth to descend (default 20). Use 0 for no limit.
 * @returns Multiline string with tree layout.
 */
export function tree(dirPath: string, maxDepth = 20): string {
    const lines: string[] = [];
    const baseName = path.basename(path.resolve(dirPath)) || path.resolve(dirPath);
    lines.push(baseName);

    function walk(currentDir: string, prefix: string, depth: number): void {
        if (maxDepth > 0 && depth >= maxDepth) return;
        let entries: fs.Dirent[];
        try {
            entries = fs.readdirSync(currentDir, { withFileTypes: true });
        } catch {
            return;
        }
        // sort: directories first, then by name
        entries.sort((a, b) => {
            const aDir = a.isDirectory() ? 0 : 1;
            const bDir = b.isDirectory() ? 0 : 1;
            if (aDir !== bDir) return aDir - bDir;
            return a.name.localeCompare(b.name, 'en', { sensitivity: 'base' });
        });
        const lastIndex = entries.length - 1;
        for (let i = 0; i < entries.length; i++) {
            const entry = entries[i];
            const isLast = i === lastIndex;
            const connector = isLast ? '└── ' : '├── ';
            lines.push(prefix + connector + entry.name);
            if (entry.isDirectory()) {
                const nextPrefix = prefix + (isLast ? '    ' : '│   ');
                walk(path.join(currentDir, entry.name), nextPrefix, depth + 1);
            }
        }
    }

    walk(path.resolve(dirPath), '', 0);
    return lines.join('\n') + '\n';
}

export function getDatasetName(rootPath: string): string {
    const finalizedPath = path.join(rootPath, 'finalized.json');
    if (!fs.existsSync(finalizedPath)) {
        console.error(`finalized.json not found at ${finalizedPath}`);
        process.exit(1);
    }
    const data = JSON.parse(fs.readFileSync(finalizedPath, 'utf8'));
    const name = data?.datasetDescription?.Name;
    if (!name || typeof name !== 'string') {
        throw new Error('datasetDescription.Name not found in finalized.json');
    }
    return safeDatasetName(name);
}

/**
 * The dataset folder name under <root>/bids: the user-supplied datasetDescription.Name without path
 * separators or leading dots, so it cannot escape <root>/bids (master #160). convert.ts uses it too.
 */
export function safeDatasetName(name: unknown): string {
    return path.basename(String(name || '')).replace(/^\.+/, '') || 'dataset';
}

/**
 * Telemetry is off by default. Setting EZBIDS_TELEMETRY_URL turns it on (never in the desktop app):
 * the files are then created and POSTed best effort (10 s per attempt, two quick retries); a failure
 * is only logged and never fails the step. (Port of master #182.)
 */
export function telemetryUrl(env: NodeJS.ProcessEnv = process.env): string | undefined {
    if (env.IS_ELECTRON === 'true') return undefined;
    const url = (env.EZBIDS_TELEMETRY_URL ?? '').trim();
    return url || undefined;
}
