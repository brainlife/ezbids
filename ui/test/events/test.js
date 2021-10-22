#!/usr/bin/env node
import fs from 'fs'
import { createEventObjects } from './lib.js'

const testdata = JSON.parse(fs.readFileSync('./testdata1.json', 'ascii'));
const ret = createEventObjects(testdata.ezbids, testdata.files);

//I am going to test the output
//TODO - check the number of objects and items
//TODO - check the first item is XYZ...

