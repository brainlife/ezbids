import { fileURLToPath } from 'url';

import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';

import Components from 'unplugin-vue-components/vite';
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers';
import ViteYaml from '@modyfi/vite-plugin-yaml';

const srcDir = fileURLToPath(new URL('./src', import.meta.url));

export default defineConfig({
    // base: '/ezbids/',
    base: './',
    resolve: {
        alias: {
            '@': srcDir,
        },
    },
    plugins: [
        vue({
            // the desktop app's in-app browser (ExternalPageDialog) is Electron's native <webview>
            template: { compilerOptions: { isCustomElement: (tag) => tag === 'webview' } },
        }),
        Components({
            resolvers: [ElementPlusResolver()],
        }),
        ViteYaml(),
    ],
    build: {
        sourcemap: true,
    },
});
