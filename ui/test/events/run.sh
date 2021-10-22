#!/bin/bash

#tsc --module system --out lib.js ../../src/libUnsafe.ts
cp ../../src/libUnsafe.ts lib.js
node test.js
