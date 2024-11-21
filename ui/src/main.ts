import { createApp } from 'vue';
import VueGtag from 'vue-gtag-next';
import App from './App.vue';
import { FontAwesomeIcon } from '@fortawesome/vue-fontawesome';
import { library } from '@fortawesome/fontawesome-svg-core';
import { faGithub } from '@fortawesome/free-brands-svg-icons';
import {
    faSpinner,
    faAngleLeft,
    faAngleRight,
    faAngleDown,
    faEye,
    faCircleCheck,
    faArrowUpRightFromSquare,
    faCircleInfo,
    faUsers,
    faBook,
    faDownload,
    faCircleQuestion,
} from '@fortawesome/free-solid-svg-icons';
import 'element-plus/dist/index.css';
import store from './store';
import api, { API } from './api/index';
import router from './routes';

// add icons
library.add(
    faSpinner,
    faGithub,
    faAngleLeft,
    faAngleRight,
    faAngleDown,
    faEye,
    faCircleCheck,
    faArrowUpRightFromSquare,
    faCircleInfo,
    faUsers,
    faBook,
    faDownload,
    faCircleQuestion
);

//move to ./types?
//tell typescript about some global properties we are adding
declare module 'vue' {
    export interface ComponentCustomProperties {
        $validate: (data: object, rule: object) => boolean;
        $store: typeof store;
        api: API;
    }
}

const app = createApp(App);
app.use(router);
app.use(store);
app.use(api);
app.use(VueGtag, {
    property: {
        id: 'G-J5H19RMNCT',
    },
});

app.component('font-awesome-icon', FontAwesomeIcon);
app.mount('#app');
