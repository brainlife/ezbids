/* Runs before each test file so modules that read env at import time see test defaults. */
process.env.BRAINLIFE_AUTHENTICATION = process.env.BRAINLIFE_AUTHENTICATION ?? 'false';
