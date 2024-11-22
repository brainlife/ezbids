import axiosInstance from '../axios.instance';

export const apihost = import.meta.env.VITE_APIHOST || '/api/ezbids';

export function getShortLivedJWTToken(sessionId: string) {
    return axiosInstance.get<string>(`${apihost}/download/${sessionId}/token`);
}
