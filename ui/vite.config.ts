import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import ViteYaml from '@modyfi/vite-plugin-yaml';

export default defineConfig({
    // base: '/ezbids/',
    base: './',
    plugins: [react(), ViteYaml()],
    server: {
        port: 3000,
        host: true,
    },
    build: {
        sourcemap: true,
    },
});
