import { createApp } from 'vue'
import VueGtag from 'vue-gtag-next'
import App from './App.vue'
import { FontAwesomeIcon } from "@fortawesome/vue-fontawesome"
import { library } from "@fortawesome/fontawesome-svg-core"
import { faGithub } from "@fortawesome/free-brands-svg-icons"
import { faSpinner, faAngleLeft, faAngleRight, faAngleDown, faEye, faCircleCheck, faArrowUpRightFromSquare, faCircleInfo } from '@fortawesome/free-solid-svg-icons'
import 'element-plus/dist/index.css'
import store from './store';
import { createRouter, createWebHistory } from 'vue-router';
import LandingPage from './LandingPage.vue';
import BaseConvertPage from './BaseConvertPage.vue';
import NotFound from './NotFound.vue';

// add icons
library.add(faGithub);
library.add(faSpinner, faAngleLeft, faAngleRight, faAngleDown, faEye, faCircleCheck, faArrowUpRightFromSquare, faCircleInfo);


//move to ./types?
//tell typescript about some global properties we are adding
declare module '@vue/runtime-core' {
  export interface ComponentCustomProperties {
    $validate: (data: object, rule: object) => boolean
    $store: typeof store
  }
}

// enable routing
const router = createRouter({
  history: createWebHistory('/ezbids'),
  routes: [
    { path: "/", component: LandingPage },
    { path: "/convert", component: BaseConvertPage },
    { path: '/:pathMatch(.*)*', component: NotFound }
  ]
})

const app = createApp(App);
app.use(router);
app.use(store)
app.use(VueGtag, {
  property: {
    id: "G-J5H19RMNCT"
  }
});

app.component("font-awesome-icon", FontAwesomeIcon)
app.mount('#app')
