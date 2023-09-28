import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'
import ViteYaml from '@modyfi/vite-plugin-yaml';

export default defineConfig({
  /* no effect?
  server: {
    port: 3001,
    hmr: {
        clientPort: 8082,
    },
  },
  */
  plugins: [
      vue(), /*vueI18nPlugin*/

      //it works on dev but dist package doesn't contain all element ui stuff
      Components({
        resolvers: [ElementPlusResolver()],
        
      }),
      ViteYaml(), // you may configure the plugin by passing in an object with the options listed below
  ],
  build: {
    sourcemap: true,
  }
})
