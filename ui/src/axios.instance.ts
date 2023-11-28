import axios from 'axios';
import { ElNotification } from 'element-plus';
import router from './routes';

const axiosInstance = axios.create({
    headers: { 'Content-Type': 'application/json; charset=UTF-8' },
});

axiosInstance.interceptors.request.use((config) => {
    const token = localStorage.getItem('jwt');
    if (token) {
        config.headers = {
            ...config.headers,
            Authorization: `Bearer ${token}`,
        };
    } else {
        ElNotification({
            title: 'Unauthorized user',
            message: '',
            type: 'error',
        });
    }
    return config;
});

axiosInstance.interceptors.response.use(
    (response) => response,
    (err) => {
        if (err.response) {
            if (err.response.status === 401) {
                router.push('/');
                ElNotification({
                    title: 'Unauthorized access',
                    message: '',
                    type: 'error',
                });
            }
        }
        throw err;
    }
);

export default axiosInstance;
