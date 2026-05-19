/* Runs before each test file so modules that read env at import time see test defaults. */
process.env.BRAINLIFE_AUTHENTICATION = process.env.BRAINLIFE_AUTHENTICATION ?? 'false';

if (typeof globalThis.File === 'undefined' && typeof Blob !== 'undefined') {
    globalThis.File = class File extends Blob {
        constructor(bits, name, options = {}) {
            super(bits, options);
            this.name = name;
            this.lastModified = options.lastModified ?? Date.now();
        }
    };
}
