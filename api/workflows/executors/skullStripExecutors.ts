import { registerToolExecutor } from '../toolRegistry';
import { spawn } from 'child_process';
import path from 'path';
import fs from 'fs';

/** Resolve the allineate binary path. Checks EZBIDS_BIN_DIR first, then a dev fallback. */
function getAllineateBin(): string {
    const binDir = process.env.EZBIDS_BIN_DIR;
    if (binDir) {
        const p = path.join(binDir, 'allineate');
        if (fs.existsSync(p)) return p;
    }
    // Dev fallback: sibling project
    const devPath = path.resolve(__dirname, '..', '..', '..', '..', 'allineate', 'allineate');
    if (fs.existsSync(devPath)) return devPath;
    return 'allineate'; // hope it's on PATH
}

/** Resolve MNI template and mask paths based on template key. */
function getTemplatePaths(templateKey: string): { template: string; mask: string } {
    const binPath = getAllineateBin();
    const binDir = path.dirname(binPath);
    if (templateKey === '55') {
        return {
            template: path.join(binDir, 'mni_icbm152_t1_tal_nlin_asym_55_ext.nii.gz'),
            mask: path.join(binDir, 'mni_icbm152_t1_tal_nlin_asym_55_ext_mask12.nii.gz'),
        };
    }
    // Default: 2mm
    return {
        template: path.join(binDir, 'MNI152_T1_2mm_ext.nii.gz'),
        mask: path.join(binDir, 'MNI152_T1_2mm_ext_mask12.nii.gz'),
    };
}

/** Run a shell command and return stdout/stderr/exit code. */
function runCommand(
    cmd: string,
    args: string[],
    env?: Record<string, string>
): Promise<{ code: number; stdout: string; stderr: string }> {
    return new Promise((resolve, reject) => {
        const proc = spawn(cmd, args, {
            env: { ...process.env, ...env },
        });
        let stdout = '';
        let stderr = '';
        proc.stdout.on('data', (d: Buffer) => {
            stdout += d.toString();
        });
        proc.stderr.on('data', (d: Buffer) => {
            stderr += d.toString();
        });
        proc.on('close', (code) => resolve({ code: code ?? 1, stdout, stderr }));
        proc.on('error', reject);
    });
}

/** Resolve the dcm2niix binary path, matching handler/utils.ts logic. */
function getDcm2niixBin(): string {
    const binDir = process.env.EZBIDS_BIN_DIR;
    const platform = process.platform === 'darwin' ? 'macos' : process.platform === 'win32' ? 'windows' : 'linux';
    const arch = process.arch === 'arm64' ? 'arm64' : 'amd64';
    const base = `dcm2niix-${platform}-${arch}`;
    const name = platform === 'windows' ? `${base}.exe` : base;
    if (binDir) {
        const p = path.resolve(path.join(binDir, 'dcm2niix', name));
        if (fs.existsSync(p)) return p;
    }
    // Fallback: try system dcm2niix
    return 'dcm2niix';
}

export function registerSkullStripExecutors(): void {
    // dcm2niix: convert DICOM folder to NIfTI
    registerToolExecutor('dcm2niix', async (inputs) => {
        const dicomFolder = inputs.dicom_folder as string;

        const bin = getDcm2niixBin();
        const args = [
            '--progress',
            'y',
            '-v',
            '1',
            '-ba',
            'n',
            '-z',
            'o',
            '-d',
            '9',
            '-f',
            'time-%t-sn-%s',
            dicomFolder,
        ];

        // eslint-disable-next-line no-console
        console.log(`[dcm2niix] Running: ${bin} ${args.join(' ')}`);
        const result = await runCommand(bin, args);

        if (result.code !== 0) {
            throw new Error(`dcm2niix failed (exit ${result.code}): ${result.stderr}`);
        }

        // Collect output .nii.gz and .json files
        const niftiFiles: string[] = [];
        const jsonSidecars: string[] = [];
        const scanDir = (dir: string) => {
            for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
                const full = path.join(dir, entry.name);
                if (entry.isDirectory()) {
                    scanDir(full);
                } else if (entry.name.endsWith('.nii.gz')) {
                    niftiFiles.push(full);
                } else if (entry.name.endsWith('.json') && !entry.name.startsWith('.')) {
                    jsonSidecars.push(full);
                }
            }
        };
        scanDir(dicomFolder);

        // eslint-disable-next-line no-console
        console.log(`[dcm2niix] Converted: ${niftiFiles.length} NIfTI files, ${jsonSidecars.length} JSON sidecars`);
        return { nifti_files: niftiFiles, json_sidecars: jsonSidecars };
    });

    // Single-volume skull strip using allineate
    registerToolExecutor('allineate-skull-strip', async (inputs) => {
        const volume = inputs.volume as string;
        const cost = (inputs.cost as string) || 'ls';
        const templatePath = inputs.template as string;
        const maskPath = inputs.mask as string;
        const stripped = volume.replace(/\.nii(\.gz)?$/, '.brain.nii.gz');

        const bin = getAllineateBin();
        // allineate <MNI_template> <input_T1> -cost <cost> -skullstrip <brain_mask> <output>
        const args = [templatePath, volume, '-cost', cost, '-skullstrip', maskPath, stripped];

        // eslint-disable-next-line no-console
        console.log(`[skull-strip] Running: ${bin} ${args.join(' ')}`);
        const result = await runCommand(bin, args, { OMP_NUM_THREADS: '4' });

        if (result.code !== 0) {
            throw new Error(`allineate skull-strip failed (exit ${result.code}): ${result.stderr}`);
        }
        if (!fs.existsSync(stripped)) {
            throw new Error(`allineate skull-strip produced no output: ${stripped}`);
        }

        return { stripped };
    });

    // Batch skull strip: loops over volumes, calls allineate-skull-strip for each
    registerToolExecutor('skull-strip-batch', async (inputs) => {
        const volumes = inputs.volumes as string[];
        const cost = (inputs.cost as string) || 'ls';
        const templateKey = (inputs.template as string) || '2mm';
        const { template, mask } = getTemplatePaths(templateKey);

        // Verify template files exist
        if (!fs.existsSync(template)) {
            throw new Error(`MNI template not found: ${template}`);
        }
        if (!fs.existsSync(mask)) {
            throw new Error(`Brain mask not found: ${mask}`);
        }

        const { getToolExecutor } = await import('../toolRegistry');
        const stripExecutor = getToolExecutor('allineate-skull-strip')!;
        const thumbExecutor = getToolExecutor('create-thumbnail');

        const stripped_volumes: string[] = [];
        const thumbnails: string[] = [];

        for (const vol of volumes) {
            // eslint-disable-next-line no-console
            console.log(`[skull-strip] Processing: ${vol}`);
            const result = await stripExecutor({
                volume: vol,
                template,
                mask,
                cost,
            });
            stripped_volumes.push(result.stripped as string);

            // Generate thumbnail for preview
            if (thumbExecutor) {
                try {
                    const thumbResult = await thumbExecutor({ volume: result.stripped as string });
                    thumbnails.push(thumbResult.thumbnail as string);
                } catch (e) {
                    // eslint-disable-next-line no-console
                    console.log(`[skull-strip] Thumbnail generation failed for ${result.stripped}: ${e}`);
                }
            }
        }

        return { stripped_volumes, thumbnails };
    });

    // Thumbnail generator: reuses handler/ezBIDS_core/createThumbnail.py
    registerToolExecutor('create-thumbnail', async (inputs) => {
        const volume = inputs.volume as string;
        const thumbnail = volume + '.png';
        const scriptDir = path.resolve(__dirname, '..', '..', '..', 'handler', 'ezBIDS_core');
        const script = path.join(scriptDir, 'createThumbnail.py');

        const result = await runCommand('python3', [script, volume, thumbnail]);
        if (result.code !== 0) {
            throw new Error(`Thumbnail creation failed: ${result.stderr}`);
        }

        return { thumbnail };
    });
}
