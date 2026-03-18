#!/usr/bin/env node
/**
 * TypeScript implementation of preprocess.sh: expand archives, rename special chars,
 * detect BIDS compliance, run validator, then either run ezBIDS_core on existing BIDS
 * or run dcm2niix/pet2bids and then ezBIDS_core.
 *
 * Usage: node preprocess.js <root> <handlerDir>
 */
import * as fs from 'fs';
import * as path from 'path';
import { execa, execaSync } from 'execa';
import {
    extractErrorBlocks,
    findBidsRoot,
    findFilesUnder,
    runRenameSpecialChars,
    gzipFile,
    intersection,
    readLines,
    runParallel,
    updateBidsignore,
} from './preprocess.utils';
import { getDcm2niixExecutablePath, log, runBidsValidator, runPython } from './utils';
import { CMD_TIMEOUT_MS } from './preprocess.consts';

const root = process.argv[2];
const handlerDir = process.argv[3];

if (!root) {
    console.error('please specify root dir');
    process.exit(1);
}

const resolvedRoot = path.resolve(root);
const resolvedHandlerDir = path.resolve(handlerDir || path.join(__dirname));

function writeBidsCompliantLog(testRoot: string, bidsCompliant: boolean): void {
    const logPath = path.join(resolvedRoot, 'bids_compliant.log');
    fs.writeFileSync(logPath, testRoot + '\n' + (bidsCompliant ? 'true' : 'false') + '\n');
}

async function runExpand(): Promise<void> {
    log('running expand (TypeScript)');
    const expandJs = path.join(resolvedHandlerDir, 'expand.js');
    try {
        await execa(process.execPath, [expandJs, resolvedRoot], {
            cwd: resolvedHandlerDir,
            stdio: 'inherit',
        });
    } catch (err: unknown) {
        const e = err as { exitCode?: number };
        throw { error: err, exitCode: e?.exitCode ?? 1 };
    }
}

async function runDcm2niix(itemPath: string): Promise<{ status: number; stderr: string }> {
    if (!itemPath.trim()) {
        log('No path provided to d2n, skipping');
        return Promise.resolve({ status: 0, stderr: '' });
    }

    log(`----------------------- ${itemPath} ------------------------`);
    const result = await execa(
        getDcm2niixExecutablePath(),
        ['--progress', 'y', '-v', '1', '-ba', 'n', '-z', 'o', '-d', '9', '-f', 'time-%t-sn-%s', itemPath],
        {
            cwd: resolvedRoot,
            reject: false,
            timeout: CMD_TIMEOUT_MS,
        }
    );
    const status = result.exitCode ?? -1;
    const stderr = result.stderr ?? '';

    if (status !== 0) {
        throw { error: new Error(`dcm2niix exited with code ${status}`), exitCode: status };
    }

    fs.appendFileSync(path.join(resolvedRoot, 'dcm2niix.done'), itemPath + '\n');
    return { status, stderr };
}

/** Run dcm2niix4pet for one path; appends to pet2bids.done on success. Uses shipped Python interpreter. */
async function runDcm2niix4Pet(itemPath: string): Promise<{ status: number; stderr: string }> {
    log(`----------------------- dcm2niix4pet: ${itemPath} ------------------------`);
    const r = await runPython(['-m', 'dcm2niix4pet', '--silent', itemPath], {
        cwd: resolvedRoot,
        timeout: CMD_TIMEOUT_MS,
        reject: true,
    });
    if (r.status === 0) {
        fs.appendFileSync(path.join(resolvedRoot, 'pet2bids.done'), itemPath + '\n');
    }
    return r;
}

/** Run ecatpet2bids for one path; appends to pet2bids.done on success. Uses shipped Python interpreter. */
async function runEcatPet2Bids(itemPath: string): Promise<{ status: number; stderr: string }> {
    log(`----------------------- ecatpet2bids: ${itemPath} ------------------------`);
    const r = await runPython(['-m', 'ecatpet2bids', itemPath, '--convert'], {
        cwd: resolvedRoot,
        timeout: CMD_TIMEOUT_MS,
    });
    if (r.status === 0) {
        fs.appendFileSync(path.join(resolvedRoot, 'pet2bids.done'), itemPath + '\n');
    }
    return r;
}

async function main(): Promise<void> {
    log(`running ${resolvedHandlerDir}/preprocess on root folder ${resolvedRoot}`);

    try {
        await runExpand();
    } catch (err) {
        console.error('Failed to run expand:');
        process.exit(1);
    }
    runRenameSpecialChars(resolvedRoot);

    log('Running bids-validator to check BIDS compliance');
    const bidsRoot = findBidsRoot(resolvedRoot);
    const testRoot = bidsRoot ?? resolvedRoot;

    updateBidsignore(testRoot);

    let bidsCompliant = false;
    try {
        const validatorLogPath = path.join(testRoot, 'validator.log');
        const { hasErr } = await runBidsValidator(false, testRoot, validatorLogPath);
        bidsCompliant = !hasErr;
    } catch (err) {
        console.error('Failed to run bids-validator:', err);
        process.exit(1);
    }

    if (!bidsCompliant) {
        log('Uploaded data is not a BIDS-compliant dataset');
    } else {
        log('Uploaded data is a BIDS-compliant dataset');
    }

    writeBidsCompliantLog(testRoot, bidsCompliant);

    if (bidsCompliant) {
        fs.writeFileSync(path.join(resolvedRoot, 'dcm2niix_output'), '');
        fs.writeFileSync(path.join(resolvedRoot, 'dcm2niix_error'), '');
        fs.writeFileSync(path.join(resolvedRoot, 'pet2bids_output'), '');
        fs.writeFileSync(path.join(resolvedRoot, 'pet2bids_error'), '');

        const nii = findFilesUnder(resolvedRoot, 9, (n) => n.endsWith('.nii.gz'));
        const blood = findFilesUnder(resolvedRoot, 9, (n) => n.endsWith('blood.json'));
        fs.writeFileSync(
            path.join(resolvedRoot, 'list'),
            [...nii, ...blood].join('\n') + (nii.length || blood.length ? '\n' : '')
        );

        log('running ezBIDS_core (may take several minutes, depending on size of data)');
        const corePy = path.join(resolvedHandlerDir, 'ezBIDS_core', 'ezBIDS_core.py');
        try {
            await runPython([corePy, resolvedRoot], { cwd: resolvedHandlerDir, reject: true });
        } catch (err) {
            console.error('Failed to run ezBIDS_core:', err);
            process.exit(1);
        }
    } else {
        log('Making sure all NIfTI files are in .nii.gz format');
        const niiFiles = findFilesUnder(resolvedRoot, 99, (n) => n.endsWith('.nii') && !n.endsWith('.nii.gz'));
        for (const rel of niiFiles) {
            const full = path.join(resolvedRoot, rel);
            if (fs.existsSync(full)) {
                try {
                    await gzipFile(full);
                } catch (err) {
                    console.error('gzip failed:', rel, err);
                    throw err;
                }
            }
        }

        log('processing ' + resolvedRoot);
        log('Finding imaging directories and files');

        if (!fs.existsSync(path.join(resolvedRoot, 'list'))) {
            fs.writeFileSync(path.join(resolvedRoot, 'list'), '');
        }
        try {
            // determine which uploaded files/folders are PET directories or ECAT files
            const findImgPy = path.join(resolvedHandlerDir, 'find_img_data.py');
            await runPython([findImgPy, resolvedRoot], { cwd: resolvedHandlerDir, reject: true });
        } catch (err) {
            console.error('find_img_data.py failed:', err);
            process.exit(1);
        }

        // sort $root/pet2bids_dcm.list, $root/pet2bids_ecat.list, and $root/dcm2niix.list for comm.
        // Then, remove pet directories from dcm2niix list
        fs.writeFileSync(path.join(resolvedRoot, 'pet2bids_output'), '');
        fs.writeFileSync(path.join(resolvedRoot, 'pet2bids.done'), '');

        const dcm2niixList = readLines(path.join(resolvedRoot, 'dcm2niix.list'));
        let removeFromDcm2niix: string[] = [];

        const pet2bidsDcmPath = path.join(resolvedRoot, 'pet2bids_dcm.list');
        if (fs.existsSync(pet2bidsDcmPath)) {
            const petDcm = readLines(pet2bidsDcmPath).sort();
            fs.writeFileSync(pet2bidsDcmPath, petDcm.join('\n') + '\n');
            log('Removing PET directories from dcm2niix list');
            removeFromDcm2niix = [...removeFromDcm2niix, ...intersection(dcm2niixList, petDcm)];
            const pet2bidsOutputPath = path.join(resolvedRoot, 'pet2bids_output');
            log('Running dcm2niix4pet');
            try {
                await runParallel(petDcm, runDcm2niix4Pet, pet2bidsOutputPath);
            } catch (err) {
                console.error('Failed to run dcm2niix4pet:', err);
                process.exit(1);
            }
        }

        const pet2bidsEcatPath = path.join(resolvedRoot, 'pet2bids_ecat.list');
        if (fs.existsSync(pet2bidsEcatPath)) {
            const petEcat = readLines(pet2bidsEcatPath).sort();
            fs.writeFileSync(pet2bidsEcatPath, petEcat.join('\n') + '\n');
            log('Removing PET ECAT files from dcm2niix list');
            removeFromDcm2niix = [...removeFromDcm2niix, ...intersection(dcm2niixList, petEcat)];
            const pet2bidsOutputPath = path.join(resolvedRoot, 'pet2bids_output');
            log('Running ecatpet2bids');
            try {
                await runParallel(petEcat, runEcatPet2Bids, pet2bidsOutputPath);
            } catch (err) {
                console.error('Failed to run ecatpet2bids:', err);
                process.exit(1);
            }
        }

        let dcm2niixFiltered = readLines(path.join(resolvedRoot, 'dcm2niix.list'));
        const removeSet = new Set(removeFromDcm2niix);
        dcm2niixFiltered = dcm2niixFiltered.filter((line) => !removeSet.has(line));
        fs.writeFileSync(path.join(resolvedRoot, 'dcm2niix.list'), dcm2niixFiltered.join('\n') + '\n');

        log('running dcm2niix');
        const dcm2niixVersion = execaSync(getDcm2niixExecutablePath(), ['--version'], {
            reject: false,
        });
        if (dcm2niixVersion.stdout) log(dcm2niixVersion.stdout.trim());

        fs.writeFileSync(path.join(resolvedRoot, 'dcm2niix.done'), '');
        const dcm2niixOutPath = path.join(resolvedRoot, 'dcm2niix_output');
        try {
            await runParallel(dcm2niixFiltered, (item) => Promise.resolve(runDcm2niix(item)), dcm2niixOutPath);
        } catch (err) {
            console.error('Failed to run dcm2niix:', err);
            process.exit(1);
        }

        const dcm2niixRan =
            fs.existsSync(path.join(resolvedRoot, 'dcm2niix.done')) &&
            fs.readFileSync(path.join(resolvedRoot, 'dcm2niix.done'), 'utf8').trim().length > 0;
        if (dcm2niixRan && fs.existsSync(dcm2niixOutPath)) {
            const outContent = fs.readFileSync(dcm2niixOutPath, 'utf8');
            fs.writeFileSync(path.join(resolvedRoot, 'dcm2niix_error'), extractErrorBlocks(outContent));
        }

        const pet2bidsRan =
            fs.existsSync(path.join(resolvedRoot, 'pet2bids.done')) &&
            fs.readFileSync(path.join(resolvedRoot, 'pet2bids.done'), 'utf8').trim().length > 0;
        const pet2bidsOutPath = path.join(resolvedRoot, 'pet2bids_output');
        if (pet2bidsRan && fs.existsSync(pet2bidsOutPath)) {
            const outContent = fs.readFileSync(pet2bidsOutPath, 'utf8');
            fs.writeFileSync(path.join(resolvedRoot, 'pet2bids_error'), extractErrorBlocks(outContent));
        }

        const nii = findFilesUnder(resolvedRoot, 9, (n) => n.endsWith('.nii.gz'));
        const blood = findFilesUnder(resolvedRoot, 9, (n) => n.endsWith('blood.json'));
        let listContent = [...nii, ...blood].join('\n');
        const megListPath = path.join(resolvedRoot, 'meg.list');
        if (fs.existsSync(megListPath)) {
            listContent += '\n' + readLines(megListPath).join('\n');
        }
        fs.writeFileSync(path.join(resolvedRoot, 'list'), listContent.replace(/^\n+/, '') + (listContent ? '\n' : ''));

        const listLines = readLines(path.join(resolvedRoot, 'list'));
        if (listLines.length === 0) {
            let errFile = '';
            const dcmErr = path.join(resolvedRoot, 'dcm2niix_error');
            const petErr = path.join(resolvedRoot, 'pet2bids_error');
            if (fs.existsSync(dcmErr) && /Error/i.test(fs.readFileSync(dcmErr, 'utf8'))) {
                errFile = 'dcm2niix_error';
            }
            if (fs.existsSync(petErr) && /Error/i.test(fs.readFileSync(petErr, 'utf8'))) {
                errFile = 'pet2bids_error';
            }
            console.error('');
            console.error('Error: Could not find any MRI, PET, or MEG imaging files in upload.');
            console.error('Please click the Debug (Download) section below and select the ' + errFile + ' file.');
            console.error(
                'Please reach out to the ezBIDS team for further assistance: https://github.com/brainlife/ezbids/issues'
            );
            process.exit(1);
        }

        // Remove .nii files that are randomly created somehow. Don't need them, as actual files are in .nii.gz format
        const niiToRemove = findFilesUnder(resolvedRoot, 99, (n) => n.endsWith('.nii'));
        for (const rel of niiToRemove) {
            const full = path.join(resolvedRoot, rel);
            if (fs.existsSync(full)) {
                try {
                    fs.unlinkSync(full);
                } catch (e) {
                    console.error('rm failed:', full, e);
                }
            }
        }

        log('running ezBIDS_core (may take several minutes, depending on size of data)');
        const ezBIDScorePy = path.join(resolvedHandlerDir, 'ezBIDS_core', 'ezBIDS_core.py');
        try {
            await runPython([ezBIDScorePy, resolvedRoot], { cwd: resolvedHandlerDir, reject: true });
        } catch (err) {
            console.error('Failed to run ezBIDS_core:', err);
            process.exit(1);
        }

        log('generating thumbnails for image sequences');
        const createThumbnailsPy = path.join(resolvedHandlerDir, 'ezBIDS_core', 'createThumbnailsMovies.py');
        const listLinesForThumb = readLines(path.join(resolvedRoot, 'list'));

        await runParallel(listLinesForThumb, async (line) => {
            const r = await runPython([createThumbnailsPy, resolvedRoot, line], {
                cwd: resolvedHandlerDir,
                reject: false, // this is not urgent, so we don't want to throw an error
            });
            if (r.status !== 0) {
                log(`Failed to generate thumbnail for ${line}: ${r.stderr}`);
            }
            return r;
        });

        log('updating ezBIDS_core.json');
        const updatePy = path.join(resolvedHandlerDir, 'ezBIDS_core', 'update_ezBIDS_core.py');
        try {
            await runPython([updatePy, resolvedRoot], { cwd: resolvedHandlerDir, reject: true });
        } catch (err) {
            console.error('Failed to run update_ezBIDS_core:', err);
            process.exit(1);
        }
    }

    log('done preprocessing');
}

main().catch((err) => {
    console.error(err);
    process.exit(1);
});
