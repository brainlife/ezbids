/**
 * Deface / skull-strip driver. Reads <workdir>/deface.json (list, method), writes deface.finished / deface.failed.
 *
 * Usage: node deface.js <root> <handlerDir>
 */
import * as fs from 'fs';
import * as path from 'path';
import { execa } from 'execa';
import { runPython } from './utils';
import { allineatePath, availableDefaceMethods, templateDir } from './deface.methods';
import { runParallel } from './preprocess.utils';

const root = process.argv[2];
const handlerDir = process.argv[3];

interface DefaceItem {
    idx: number;
    path?: string;
}

interface DefaceJson {
    method: string;
    list: DefaceItem[];
}

function die(msg: string): never {
    // eslint-disable-next-line no-console -- CLI
    console.error(msg);
    process.exit(1);
}

if (!root) die('please specify root dir');

const workRoot = path.resolve(root);
const resolvedHandlerDir = path.resolve(handlerDir || path.join(__dirname));

function resolveVolume(p: string): string {
    if (path.isAbsolute(p)) return path.normalize(p);
    return path.resolve(workRoot, p.replace(/^\.\//, ''));
}

function cancelRequested(): boolean {
    return fs.existsSync(path.join(workRoot, '.cancel'));
}

function appendLine(file: string, line: string): void {
    fs.appendFileSync(file, `${line}\n`);
}

/** MNI template + face mask (handler/templates). */
function getTemplatePaths(): { template: string; mask: string } {
    const dir = templateDir();
    return {
        template: path.join(dir, 'mean_reg2mean.nii.gz'),
        mask: path.join(dir, 'facemask.nii.gz'),
    };
}

async function canonicalizeNiftiInPlace(niftiPath: string, resolvedHandler: string): Promise<void> {
    const scriptDir = path.join(resolvedHandler, 'ezBIDS_core');
    const script = path.join(scriptDir, 'canonicalizeNifti.py');
    const { status, stderr } = await runPython([script, niftiPath], {
        cwd: scriptDir,
        timeout: 100000,
    });
    if (status !== 0) {
        throw new Error(stderr || 'canonicalizeNifti failed');
    }
}

async function thumbnailForNifti(niftiPath: string, resolvedHandler: string): Promise<void> {
    const scriptDir = path.join(resolvedHandler, 'ezBIDS_core');
    const script = path.join(scriptDir, 'createThumbnail.py');
    const pngPath = `${niftiPath}.png`;
    const { status, stderr } = await runPython([script, niftiPath, pngPath], {
        cwd: scriptDir,
        timeout: 100000,
    });
    if (status !== 0) {
        throw new Error(stderr || 'createThumbnail failed');
    }
}

/**
 * Canonicalize the volume in place (nibabel as_closest_canonical), then run allineate skull-strip:
 * MNI template + input volume + mask → stripped brain; output is renamed to `<vol>.defaced.nii.gz`.
 */
export async function runAllineateDefacing(vol: string, resolvedHandler: string, cost = 'ls'): Promise<void> {
    await canonicalizeNiftiInPlace(vol, resolvedHandler);

    const { template, mask } = getTemplatePaths();
    if (!fs.existsSync(template)) {
        throw new Error(`MNI template not found: ${template}`);
    }
    if (!fs.existsSync(mask)) {
        throw new Error(`Brain mask not found: ${mask}`);
    }

    const stripped = vol.replace(/\.nii(\.gz)?$/i, '.brain.nii.gz');
    const allineate = allineatePath();
    const args = [template, vol, '-cost', cost, '-skullstrip', mask, stripped];

    // eslint-disable-next-line no-console -- CLI
    console.log(`[allineate] ${allineate} ${args.join(' ')}`);
    try {
        await execa(allineate, args, {
            stdio: 'inherit',
            env: { ...process.env, OMP_NUM_THREADS: '4' },
        });
    } catch (e) {
        console.error('allineate failed:', allineate, args, e);
        throw e;
    }

    if (!fs.existsSync(stripped)) {
        throw new Error(`allineate produced no output: ${stripped}`);
    }

    const defaced = `${vol}.defaced.nii.gz`;
    fs.renameSync(stripped, defaced);

    const brainPng = `${stripped}.png`;
    if (fs.existsSync(brainPng)) {
        fs.unlinkSync(brainPng);
    }

    await thumbnailForNifti(defaced, resolvedHandler);
}

/**
 * master's deface.sh, per image: fslreorient2std in place, then
 * quickshear: ROBEX brain mask + quickshear (60 s limit); pydeface: FSL face-mask registration.
 */
export async function runFslDefacing(method: 'quickshear' | 'pydeface', vol: string, resolvedHandler: string): Promise<void> {
    const opts = { stdio: 'inherit' as const, cwd: path.dirname(vol) };
    await execa('fslreorient2std', [vol, vol], opts);
    const defaced = `${vol}.defaced.nii.gz`;
    if (method === 'quickshear') {
        const mask = `${vol}.mask.nii.gz`;
        await execa('runROBEX.sh', [vol, mask], opts);
        await execa('quickshear', [vol, mask, defaced], { ...opts, timeout: 60_000 });
    } else {
        await execa('pydeface', ['--verbose', '--force', vol, '--outfile', defaced], opts);
    }
    if (!fs.existsSync(defaced)) throw new Error(`${method} produced no output: ${defaced}`);
    await thumbnailForNifti(defaced, resolvedHandler);
}

async function main(): Promise<void> {
    const defaceJsonPath = path.join(workRoot, 'deface.json');
    if (!fs.existsSync(defaceJsonPath)) {
        die(`missing ${defaceJsonPath}`);
    }

    const body = JSON.parse(fs.readFileSync(defaceJsonPath, 'utf8')) as DefaceJson;
    const method = body.method;
    const list = body.list || [];

    const finishedPath = path.join(workRoot, 'deface.finished');
    const failedPath = path.join(workRoot, 'deface.failed');
    fs.writeFileSync(finishedPath, '');
    fs.writeFileSync(failedPath, '');

    let anyFailed = false;

    const available = availableDefaceMethods();
    if (!available.includes(method as never)) {
        die(`deface method "${method}" is not available here (available: ${available.join(', ') || 'none'})`);
    }

    async function processItem(item: DefaceItem): Promise<{ status: number; stderr: string }> {
        if (cancelRequested()) {
            // eslint-disable-next-line no-console -- CLI
            console.log('cancel requested; stopping deface loop');
            process.exit(1);
        }

        const rel = item.path;
        if (!rel) {
            anyFailed = true;
            appendLine(failedPath, String(item.idx));
            return { status: 1, stderr: `missing relative path for idx=${item.idx}` };
        }

        const vol = resolveVolume(rel);
        if (!fs.existsSync(vol)) {
            // eslint-disable-next-line no-console -- CLI
            console.error(`missing volume: ${vol}`);
            anyFailed = true;
            appendLine(failedPath, String(item.idx));
            return { status: 1, stderr: `missing volume: ${vol}` };
        }

        try {
            if (method === 'allineate') await runAllineateDefacing(vol, resolvedHandlerDir);
            else await runFslDefacing(method as 'quickshear' | 'pydeface', vol, resolvedHandlerDir);
            appendLine(finishedPath, String(item.idx));
            return { status: 0, stderr: '' };
        } catch (e) {
            // eslint-disable-next-line no-console -- CLI
            console.error(e);
            anyFailed = true;
            appendLine(failedPath, String(item.idx));
            return { status: 1, stderr: String(e) };
        }
    }

    await runParallel(list, processItem, failedPath);

    // eslint-disable-next-line no-console -- CLI
    console.log('all done defacing');
    if (anyFailed) {
        // eslint-disable-next-line no-console -- CLI
        console.error('deface finished with one or more failures');
        process.exit(1);
    }
}

main().catch((e) => {
    console.error(e);
    process.exit(1);
});
