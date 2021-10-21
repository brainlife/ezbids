import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

//import Components from 'unplugin-vue-components/vite'
//import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'

/*
const vueI18nPlugin = {
  name: 'vue-i18n',
  transform(code, id) {
    if (!/vue&type=i18n/.test(id)) {
      return
    }
    if (/\.ya?ml$/.test(id)) {
      code = JSON.stringify(require('js-yaml').safeLoad(code.trim()))
    }
    return `export default Comp => {
      Comp.i18n = ${code}
    }`
  }
}
*/

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
      vue(), /*vueI18nPlugin*/

      //it works on dev but dist package doesn't contain all element ui stuff
      /*
      Components({
        resolvers: [ElementPlusResolver()],
      }),
      */
  ],
  build: {
    sourcemap: true,
  }
})
