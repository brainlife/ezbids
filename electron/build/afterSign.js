/* eslint-env node */
/* eslint-disable @typescript-eslint/no-var-requires, no-console */

const fs = require('fs');
const path = require('path');
const { execFileSync, spawnSync } = require('child_process');

function walkFiles(rootDir, out = []) {
    if (!fs.existsSync(rootDir)) return out;
    for (const entry of fs.readdirSync(rootDir, { withFileTypes: true })) {
        const fullPath = path.join(rootDir, entry.name);
        if (entry.isDirectory()) {
            walkFiles(fullPath, out);
        } else if (entry.isFile()) {
            out.push(fullPath);
        }
    }
    return out;
}

function isMachO(filePath) {
    try {
        const desc = execFileSync('file', ['-b', filePath], { encoding: 'utf8' });
        return desc.includes('Mach-O');
    } catch {
        return false;
    }
}

function detectSigningIdentity(appPath) {
    if (process.env.CSC_NAME && process.env.CSC_NAME.trim()) return process.env.CSC_NAME.trim();

    const result = spawnSync('codesign', ['-dv', '--verbose=4', appPath], {
        encoding: 'utf8',
        stdio: ['ignore', 'pipe', 'pipe'],
    });
    const info = `${result.stdout || ''}\n${result.stderr || ''}`;
    if (!info.trim()) {
        throw new Error('Unable to inspect app signature with codesign.');
    }

    const line = info
        .split('\n')
        .find(
            (l) => l.startsWith('Authority=Developer ID Application:') || l.startsWith('Authority=Apple Development:')
        );
    if (!line) {
        throw new Error('Could not detect signing identity from app bundle (codesign Authority line missing).');
    }
    return line.replace('Authority=', '').trim();
}

module.exports = async function afterSign(context) {
    if (context.electronPlatformName !== 'darwin') return;
    if (process.env.CSC_IDENTITY_AUTO_DISCOVERY === 'false') {
        console.log('[afterSign] Signing disabled (CSC_IDENTITY_AUTO_DISCOVERY=false); skipping nested binary signing');
        return;
    }
    console.log('[afterSign] Signing enabled (CSC_IDENTITY_AUTO_DISCOVERY=true); performing nested binary signing');

    const appName = context.packager.appInfo.productFilename;
    const appPath = path.join(context.appOutDir, `${appName}.app`);
    const binDir = path.join(appPath, 'Contents', 'Resources', 'bin');
    const appResourcesDir = path.join(appPath, 'Contents', 'Resources', 'app');
    const entitlementsPath = path.join(context.packager.projectDir, 'build', 'entitlements.mac.plist');
    const scanRoots = [binDir, appResourcesDir];
    const existingRoots = scanRoots.filter((p) => fs.existsSync(p));

    if (existingRoots.length === 0) {
        console.log('[afterSign] No scan roots found under Contents/Resources; skipping nested binary signing');
        return;
    }

    let identity;
    try {
        identity = detectSigningIdentity(appPath);
    } catch (err) {
        console.log(`[afterSign] Skipping nested binary signing: ${err.message}`);
        return;
    }
    const allFiles = [];
    for (const root of existingRoots) walkFiles(root, allFiles);
    const machoFiles = allFiles.filter(isMachO);
    console.log(`[afterSign] Found ${machoFiles.length} Mach-O file(s) under ${existingRoots.join(', ')}`);

    for (const filePath of machoFiles) {
        const args = [
            '--force',
            '--sign',
            identity,
            '--timestamp',
            '--options',
            'runtime',
            '--entitlements',
            entitlementsPath,
            filePath,
        ];
        execFileSync('codesign', args, { stdio: 'inherit' });
    }

    execFileSync('codesign', ['--verify', '--deep', '--strict', '--verbose=2', appPath], { stdio: 'inherit' });
    console.log('[afterSign] Nested binary signing completed');
};
