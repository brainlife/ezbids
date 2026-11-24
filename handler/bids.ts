#!/usr/bin/env node
/**
 * TypeScript port of bids.sh: run MEG conversion, convert to BIDS, run validator,
 * copy template; telemetry only when EZBIDS_TELEMETRY_URL is set (off by default).
 *
 * Usage: node bids.js <root> [handlerDir]
 */
import * as fs from 'fs';
import * as path from 'path';
import { getDatasetName, telemetryUrl, tree } from './bids.utils';
import { log, resolveHandlerScript, runBidsValidator, runNodeScript, runPython } from './utils';

const rootArg = process.argv[2];
const handlerDirArg = process.argv[3];

if (!rootArg) {
    console.error('please specify root dir');
    process.exit(1);
}

const root = path.resolve(rootArg);
const handlerDir = path.resolve(handlerDirArg || path.join(__dirname));

// Telemetry: see telemetryUrl() in bids.utils.ts (off by default, never in the desktop app).
async function postTelemetryFile(url: string, filePath: string): Promise<void> {
    if (!fs.existsSync(filePath)) return;
    const body = fs.readFileSync(filePath, 'utf8');
    const name = path.basename(filePath);
    for (let attempt = 0; attempt < 3; attempt++) {
        try {
            const res = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body,
                signal: AbortSignal.timeout(10_000),
            });
            if (res.ok) return;
            log(`telemetry POST failed for ${name}: ${res.status}`);
            return;
        } catch (err) {
            if (attempt === 2) log(`telemetry not sent (${name}): server unreachable (${err})`);
        }
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
    const convertPath = resolveHandlerScript('convert', handlerDir);
    try {
        await runNodeScript([convertPath, root], {
            cwd: handlerDir,
        });
    } catch (err) {
        console.error(`Failed to run ${convertPath}:`, err);
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

    const url = telemetryUrl();
    if (url) {
        log('Creating ezBIDS telemetry files');
        if (fs.existsSync(telemetryPy)) {
            await runPython([telemetryPy, root], {
                cwd: handlerDir,
                stdio: 'inherit',
                reject: false,
            });
        }
        await postTelemetryFile(url, validatorJson);
        await postTelemetryFile(url, path.join(root, 'ezBIDS_core_telemetry.json'));
        await postTelemetryFile(url, path.join(root, 'ezBIDS_finalized_telemetry.json'));
    }
}

main().catch((err) => {
    console.error(err);
    process.exit(1);
});
