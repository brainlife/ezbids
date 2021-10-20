import { ComponentCustomProperties } from 'vue'
import { Store } from 'vuex'
import state from './store'

declare module '@vue/runtime-core' {
  // provide typings for `this.$store`
  interface ComponentCustomProperties {
    $store: Store<state>
    //$notify: (conf: {title: string, message: string})=>{}
  }
}
