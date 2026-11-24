import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { availableDefaceMethods, writeDefaceMethods } from './deface.methods';

function exe(dir: string, name: string): void {
    fs.writeFileSync(path.join(dir, name), '#!/bin/sh\n', { mode: 0o755 });
}

describe('availableDefaceMethods (from the tools the handler finds)', () => {
    let tmp: string, bin: string, tools: string, tpl: string;
    beforeEach(() => {
        tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'ezbids-deface-'));
        bin = path.join(tmp, 'bin');
        tools = path.join(tmp, 'tools');
        tpl = path.join(tmp, 'templates');
        for (const d of [path.join(bin, 'allineate'), tools, tpl]) fs.mkdirSync(d, { recursive: true });
        fs.writeFileSync(path.join(tpl, 'mean_reg2mean.nii.gz'), '');
        fs.writeFileSync(path.join(tpl, 'facemask.nii.gz'), '');
    });
    afterEach(() => fs.rmSync(tmp, { recursive: true, force: true }));
    const env = (extra: NodeJS.ProcessEnv = {}): NodeJS.ProcessEnv => ({
        PATH: tools,
        EZBIDS_BIN_DIR: bin,
        EZBIDS_PLATFORM: 'linux',
        EZBIDS_ARCH: 'amd64',
        EZBIDS_TEMPLATE_DIR: tpl,
        ...extra,
    });

    it('web image: quickshear, pydeface and allineate when all tools are there', () => {
        for (const t of ['fslreorient2std', 'runROBEX.sh', 'quickshear', 'pydeface']) exe(tools, t);
        exe(path.join(bin, 'allineate'), 'allineate-linux-amd64');
        expect(availableDefaceMethods(env())).toEqual(['quickshear', 'pydeface', 'allineate']);
    });

    it('no FSL: no quickshear or pydeface', () => {
        exe(tools, 'quickshear');
        exe(tools, 'runROBEX.sh');
        exe(path.join(bin, 'allineate'), 'allineate-linux-amd64');
        expect(availableDefaceMethods(env())).toEqual(['allineate']);
    });

    it('desktop: allineate only, even with FSL on PATH', () => {
        for (const t of ['fslreorient2std', 'runROBEX.sh', 'quickshear', 'pydeface']) exe(tools, t);
        exe(path.join(bin, 'allineate'), 'allineate-linux-amd64');
        expect(availableDefaceMethods(env({ IS_ELECTRON: 'true' }))).toEqual(['allineate']);
    });

    it('writes deface-methods.json for the API', () => {
        exe(path.join(bin, 'allineate'), 'allineate-linux-amd64');
        const wd = path.join(tmp, 'work');
        expect(writeDefaceMethods(wd, env())).toEqual(['allineate']);
        expect(JSON.parse(fs.readFileSync(path.join(wd, 'deface-methods.json'), 'utf8'))).toEqual({ methods: ['allineate'] });
    });
});
