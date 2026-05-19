#!/usr/bin/env node
/**
 * Layer 1 smoke entrypoint: runs e2e/smoke-bundled-runtime.test.ts under Jest with EZBIDS_SMOKE_BUNDLED=1.
 * Expect EZBIDS_BIN_DIR, EZBIDS_PLATFORM, EZBIDS_ARCH (and optionally BIDS_VALIDATOR_PATH) in the environment.
 */
import { spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const require = createRequire(import.meta.url);
const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const jestBin = require.resolve('jest/bin/jest');
const smokeTest = join(root, 'e2e', 'smoke-bundled-runtime.test.ts');

const env = {
    ...process.env,
    EZBIDS_SMOKE_BUNDLED: '1',
};

const result = spawnSync(
    process.execPath,
    [jestBin, smokeTest, '--runInBand', '--forceExit'],
    { cwd: root, env, stdio: 'inherit' }
);

if (result.error) {
    console.error(result.error);
    process.exit(1);
}
process.exit(result.status === null ? 1 : result.status);
