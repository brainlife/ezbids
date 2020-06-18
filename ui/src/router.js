import Vue from 'vue'
import Router from 'vue-router'
import App from './App.vue'

Vue.use(Router)

export default new Router({
    //mode: 'history',
    routes: [
        /*
        {path: '/upload', component: upload, },
        {path: '/description', component: description, },
        {path: '/participants', component: participants, },
        {path: '/objects', component: objects, },
        */
        {path: '/', component: App},
    ]
});



