#!/bin/bash

bet2_js_url="https://raw.githubusercontent.com/wpmed92/WebMRI/master/src/app/src/brainbrowser/volume-viewer/plugins/bet2.js"
bet2_wasm_url="https://github.com/wpmed92/WebMRI/raw/master/src/app/src/brainbrowser/volume-viewer/workers/bet2.wasm"

curl -L -o edge/bet2.js $bet2_js_url
curl -L -o edge/bet2.wasm $bet2_wasm_url
sed -i '' -e '1s/^/export /' -e 's/=\"bet2\.wasm\"/=Module["wasmPath"]/g' edge/bet2.js
