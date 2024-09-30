import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';

import Components from 'unplugin-vue-components/vite';
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers';
import ViteYaml from '@modyfi/vite-plugin-yaml';

export default defineConfig({
    base: '/ezbids/',
    mode: 'production',
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
    server: {
        hmr: false,
        strictPort: true,
        port: 3000,
    },
});
