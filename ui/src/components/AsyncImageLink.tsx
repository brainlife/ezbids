import React, { useEffect, useState } from 'react';
import axios from '../axios.instance';
import { useAppSelector } from '../store/hooks';

interface AsyncImageLinkProps {
    path: string;
}

const AsyncImageLink: React.FC<AsyncImageLinkProps> = ({ path }) => {
    const session = useAppSelector((state) => state.session.data);
    const config = useAppSelector((state) => state.session.config);
    const [pathWithToken, setPathWithToken] = useState('');

    const getURL = (p: string | undefined) => {
        if (!p || !session?._id) return '';
        return `${config.apihost}/download/${session._id}/${p}`;
    };

    const updatePathWithToken = () => {
        if (!session?._id) return;
        axios
            .get<string>(`${config.apihost}/download/${session._id}/token`)
            .then((res) => {
                setPathWithToken(`${getURL(path)}?token=${res.data}`);
            })
            .catch((err) => {
                console.error(err);
            });
    };

    useEffect(() => {
        updatePathWithToken();
    }, [path, session?._id, config.apihost]);

    const handleGoToLink = () => {
        if (!session?._id) return;
        axios.get<string>(`${config.apihost}/download/${session._id}/token`).then((res) => {
            window.location.href = `${getURL(path)}?token=${res.data}`;
        });
    };

    return (
        <div>
            <a style={{ cursor: 'pointer' }} onClick={handleGoToLink}>
                {pathWithToken && <img style={{ width: '100%' }} src={pathWithToken} alt="...loading" />}
            </a>
        </div>
    );
};

export default AsyncImageLink;
