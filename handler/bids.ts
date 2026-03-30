#!/usr/bin/env node
/**
 * TypeScript port of bids.sh: run MEG conversion, convert to BIDS, run validator,
 * copy template, create telemetry files, and optionally POST telemetry to server.
 *
 * Usage: node bids.js <root> [handlerDir]
 */
import * as fs from 'fs';
import * as path from 'path';
import { execa } from 'execa';
import { getBinPath, log, runBidsValidator, runPython } from './utils';
import { getDatasetName, tree } from './bids.utils';

const rootArg = process.argv[2];
const handlerDirArg = process.argv[3];

if (!rootArg) {
    console.error('please specify root dir');
    process.exit(1);
}

const root = path.resolve(rootArg);
const handlerDir = path.resolve(handlerDirArg || path.join(__dirname));

const TELEMETRY_URL = 'http://52.87.154.236/telemetry/';

async function postTelemetryFile(filePath: string): Promise<void> {
    if (!fs.existsSync(filePath)) return;
    const body = fs.readFileSync(filePath, 'utf8');
    try {
        const res = await fetch(TELEMETRY_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body,
        });
        if (!res.ok) {
            log(`telemetry POST failed for ${path.basename(filePath)}: ${res.status}`);
        }
    } catch (err) {
        log(`telemetry POST error for ${path.basename(filePath)}: ${err}`);
    }
}

async function main(): Promise<void> {
    const datasetName = getDatasetName(root);
    const rootDir = path.join(root, 'bids', datasetName);

    // Clean up from previous run
    const bidsDir = path.join(root, 'bids');
    if (fs.existsSync(bidsDir)) {
        fs.rmSync(bidsDir, { recursive: true, force: true });
    }

    const pythonPath = getBinPath('python-runtime');
    const telemetryPy = path.join(handlerDir, 'telemetry.py');

    // Run MEG BIDS conversion if relevant data found
    log('converting MEG data (if present)');
    const convertMegPy = path.join(handlerDir, 'convert_meg.py');
    try {
        await runPython([convertMegPy, path.join(root, 'finalized.json'), rootDir], {
            cwd: handlerDir,
            reject: true,
        });
    } catch (err) {
        console.error('Failed to run convert_meg.py:', err);
        process.exit(1);
    }

    // Convert output to BIDS
    log('converting output to bids');
    const convertPath = process.env.EZBIDS_CONVERT_PATH ?? path.join(handlerDir, 'convert.js');
    try {
        await execa(process.execPath, [convertPath, root], {
            cwd: handlerDir,
            stdio: 'inherit',
            reject: true,
        });
    } catch (err) {
        console.error('Failed to run convert.js:', err);
        process.exit(1);
    }

    // Output BIDS directory structure
    log('output bids directory structure');
    const treeLog = path.join(root, 'tree.log');
    fs.writeFileSync(treeLog, tree(rootDir));

    // Run BIDS validator
    log('running bids validator');
    const validatorJson = path.join(rootDir, 'validator.json');
    try {
        await runBidsValidator(true, rootDir, validatorJson);
    } catch (err) {
        console.error('Failed to run bids validator:', err);
        process.exit(1);
    }

    // Copy finalized.json to ezBIDS_template.json
    log('Copying finalized.json file to ezBIDS_template.json');
    fs.copyFileSync(path.join(root, 'finalized.json'), path.join(root, 'ezBIDS_template.json'));

    // Telemetry (to hard-coded pet2bids server) - skip when running in Electron as we are doing local processing
    if (process.env.IS_ELECTRON !== 'true') {
        // Create telemetry-specific files
        log('Creating ezBIDS telemetry files');
        if (fs.existsSync(telemetryPy)) {
            await execa(pythonPath, [telemetryPy, root], {
                cwd: handlerDir,
                stdio: 'inherit',
                reject: false,
            });
        }
        await postTelemetryFile(validatorJson);
        await postTelemetryFile(path.join(root, 'ezBIDS_core_telemetry.json'));
        await postTelemetryFile(path.join(root, 'ezBIDS_finalized_telemetry.json'));
    }
}

main().catch((err) => {
    console.error(err);
    process.exit(1);
});
