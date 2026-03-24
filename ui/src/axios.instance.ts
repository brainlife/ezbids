import axios from 'axios';
import toast from 'react-hot-toast';
import { hasAuth } from './lib';

const axiosInstance = axios.create({
    // Don't set a default Content-Type — let axios auto-detect
    // (multipart/form-data for FormData, application/json for objects)
});

axiosInstance.interceptors.request.use((config) => {
    if (!hasAuth()) return config;
    const token = localStorage.getItem('jwt');
    if (token) {
        config.headers.set('Authorization', `Bearer ${token}`);
    } else {
        toast.error('Unauthorized user');
    }
    return config;
});

axiosInstance.interceptors.response.use(
    (response) => response,
    (err) => {
        if (err.response) {
            if (err.response.status === 401) {
                toast.error('Unauthorized access');
                // Navigation handled at component level via React Router
                window.location.href = '/ezbids/';
            }
        }
        throw err;
    }
);

export default axiosInstance;
