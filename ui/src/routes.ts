import { createRouter, createWebHistory } from 'vue-router';
import LandingPage from './LandingPage.vue';
import BaseConvertPage from './BaseConvertPage.vue';
import NotFound from './NotFound.vue';
import { hasJWT } from './lib';
import { ElNotification } from 'element-plus';

// enable routing
const router = createRouter({
    history: createWebHistory('/ezbids'),
    routes: [
        { path: '/', name: 'base', component: LandingPage },
        { path: '/convert', name: 'convert', component: BaseConvertPage },
        { path: '/:pathMatch(.*)*', component: NotFound },
    ],
});

router.beforeEach((to, from) => {
    if (!hasJWT() && to.name !== 'base') {
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
