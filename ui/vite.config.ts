import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';

import Components from 'unplugin-vue-components/vite';
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers';
import ViteYaml from '@modyfi/vite-plugin-yaml';
import wasm from 'vite-plugin-wasm';
import topLevelAwait from 'vite-plugin-top-level-await';

export default defineConfig({
    base: '/ezbids/',
    plugins: [
        vue(),
        Components({
            resolvers: [ElementPlusResolver()],
        }),
        ViteYaml(),
    ],
    build: {
        sourcemap: true,
    },
    optimizeDeps: {
        exclude: ['@niivue/dcm2niix'],
    },
    worker: {
        plugins: [wasm(), topLevelAwait()],
        format: 'es',
    },
});
