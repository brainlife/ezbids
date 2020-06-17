import Vue from 'vue'
import Router from 'vue-router'

import upload from '@/upload'
import preprocess from '@/preprocess'
import description from '@/description'
import participants from '@/participants'
import objects from '@/objects'

Vue.use(Router)

export default new Router({
    mode: 'history',
    routes: [
        {path: '/', redirect: '/upload'},

        {path: '/upload', component: upload, },
        {path: '/preprocess', component: preprocess, },
        {path: '/description', component: description, },
        {path: '/participants', component: participants, },
        {path: '/objects', component: objects, },
    ]
});



