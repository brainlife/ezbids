#!/usr/bin/env node
import fs from 'fs'
import { createEventObjects } from './lib.js'

const testdata = JSON.parse(fs.readFileSync('./OpenSciencetest.json', 'utf8'));
const ret = createEventObjects(testdata.ezbids, testdata.files);

console.log(JSON.stringify(ret.cool, null, 4))

//I am going to test the output
//TODO - check the number of objects and items
//TODO - check the first item is XYZ...

