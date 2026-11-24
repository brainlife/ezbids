'use strict';

/** Minimal p-limit compatible shim for Jest (real p-limit v6+ is ESM-only). */
module.exports = function pLimit() {
    return function run(fn) {
        return fn();
    };
};
