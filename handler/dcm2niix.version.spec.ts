/**
 * dcm2niix has one pin, handler/dcm2niix.env, read by handler/Dockerfile (web image) and fetch-binaries.sh
 * (desktop app). This fails when any other dcm2niix release tag (v1.0.YYYYMMDD) is written in the repo's
 * code, scripts, workflows or docs. Recorded conversion outputs (test fixtures with ConversionSoftwareVersion)
 * are data, not a pin, and are skipped.
 */
import { execFileSync } from 'child_process';
import * as fs from 'fs';
import * as path from 'path';

const ROOT = path.resolve(__dirname, '..');
const ENV = fs.readFileSync(path.join(__dirname, 'dcm2niix.env'), 'utf8');
const PINNED = /^DCM2NIIX_VERSION=(\S+)$/m.exec(ENV)?.[1];
const TAG = /\bv1\.0\.20\d{6}[a-z]?\b/g;
const SKIP = [
    /(^|\/)tests?\/.*\.json$/, // recorded sidecars / ezBIDS output (ConversionSoftwareVersion)
    /(^|\/)tests?\/fixtures\//,
    /\.lock$/,
    /package-lock\.json$/,
    /\.(png|jpe?g|gif|svg|pdf|zip|gz|nii)$/i,
];

describe('dcm2niix version pin', () => {
    it('has a pinned tag and a sha256 for every platform it supports', () => {
        expect(PINNED).toMatch(/^v1\.0\.20\d{6}[a-z]?$/);
        for (const p of ['linux_amd64', 'darwin_arm64', 'darwin_amd64', 'windows_amd64']) {
            expect(ENV).toMatch(new RegExp(`^DCM2NIIX_ASSET_${p}=dcm2niix_\\w+\\.zip$`, 'm'));
            expect(ENV).toMatch(new RegExp(`^DCM2NIIX_SHA256_${p}=[0-9a-f]{64}$`, 'm'));
        }
    });

    it('no other dcm2niix tag is written anywhere in the repo', () => {
        const files = execFileSync('git', ['ls-files'], { cwd: ROOT, encoding: 'utf8' })
            .split('\n')
            .filter((f) => f && !SKIP.some((re) => re.test(f)));
        const stale: string[] = [];
        for (const f of files) {
            const full = path.join(ROOT, f);
            let text: string;
            try {
                if (!fs.statSync(full).isFile() || fs.statSync(full).size > 2_000_000) continue;
                text = fs.readFileSync(full, 'utf8');
            } catch {
                continue;
            }
            for (const m of text.match(TAG) ?? []) if (m !== PINNED) stale.push(`${f}: ${m}`);
        }
        expect(stale).toEqual([]);
    });
});
