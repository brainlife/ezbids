/* eslint-env node */
/** @type {import('jest').Config} */
// p-limit v6+ is ESM-only; the shim avoids transforming node_modules.
module.exports = {
    preset: 'ts-jest',
    testEnvironment: 'node',
    roots: ['<rootDir>'],
    testMatch: ['<rootDir>/api/**/*.test.ts', '<rootDir>/handler/**/*.test.ts', '<rootDir>/ui/src/**/*.test.ts'],
    modulePathIgnorePatterns: [
        '<rootDir>/build/',
        '<rootDir>/electron/dist/',
        '<rootDir>/electron/release/',
        '<rootDir>/ui/dist/',
    ],
    moduleNameMapper: {
        '^p-limit$': '<rootDir>/test/shims/p-limit.cjs',
    },
    setupFiles: ['<rootDir>/jest.setup.cjs'],
    transform: {
        '^.+\\.tsx?$': [
            'ts-jest',
            {
                tsconfig: '<rootDir>/tsconfig.jest.json',
                diagnostics: false,
            },
        ],
    },
};
