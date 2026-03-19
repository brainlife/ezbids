import { createRouter, createWebHistory, createWebHashHistory } from 'vue-router';
import LandingPage from './LandingPage.vue';
import BaseConvertPage from './BaseConvertPage.vue';
import NotFound from './NotFound.vue';
import { hasJWT, authRequired } from './lib';
import { ElNotification } from 'element-plus';

const isElectron = window.env.IS_ELECTRON === 'true';

const router = createRouter({
    history: isElectron ? createWebHashHistory() : createWebHistory('/ezbids'),
    routes: [
        { path: '', name: 'base', component: LandingPage },
        { path: '/', component: LandingPage },
        { path: '/convert', name: 'convert', component: BaseConvertPage },
        { path: '/:pathMatch(.*)*', component: NotFound },
    ],
});

router.beforeEach((to, from) => {
    if (authRequired() && !hasJWT() && to.name !== 'base') {
        ElNotification({
            title: 'Please login to continue',
            message: '',
            type: 'error',
        });
        return { name: 'base' }; // route back to landing page
    }
    return true;
});

export default router;
