import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

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
  plugins: [vue(), /*vueI18nPlugin*/],
  build: {
    sourcemap: true,
  }
})
