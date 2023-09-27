import { createApp } from 'vue'

import VueGtag from 'vue-gtag-next'

import App from './App.vue'

import { FontAwesomeIcon } from "@fortawesome/vue-fontawesome"
import { library } from "@fortawesome/fontawesome-svg-core"
import { faGithub } from "@fortawesome/free-brands-svg-icons"
library.add(faGithub);

import { faSpinner, faAngleLeft, faAngleRight, faEye, faCircleInfo } from '@fortawesome/free-solid-svg-icons'
library.add(faSpinner, faAngleLeft, faAngleRight, faEye, faCircleInfo );


import 'element-plus/dist/index.css'

import store from './store'

//move to ./types?
//tell typescript about some global properties we are adding
declare module '@vue/runtime-core' {
    export interface ComponentCustomProperties {
      $validate: (data: object, rule: object) => boolean
      $store: typeof store
    }
}

const app = createApp(App);
app.use(store)
app.use(VueGtag, {
    property: {
      id: "G-J5H19RMNCT"
    }
});

app.component("font-awesome-icon", FontAwesomeIcon)
app.mount('#app')
