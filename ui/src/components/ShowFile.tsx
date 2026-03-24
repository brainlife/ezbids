import React, { useEffect, useState } from 'react';
// @ts-ignore
import Convert from 'ansi-to-html';
import axios from '../axios.instance';
import { useAppSelector } from '../store/hooks';

const convert = new Convert();

interface ShowFileProps {
    path: string;
    tall?: boolean;
}

const ShowFile: React.FC<ShowFileProps> = ({ path, tall = false }) => {
    const session = useAppSelector((state) => state.session.data);
    const config = useAppSelector((state) => state.session.config);
    const [content, setContent] = useState('');

    const maxHeight = tall ? '400px' : '200px';

    useEffect(() => {
        if (!session?._id || !path) return;

        axios
            .get(`${config.apihost}/download/${session._id}/token`)
            .then((res) => {
                const shortLivedJWT = res.data;
                return axios.get(`${config.apihost}/download/${session._id}/${path}?token=${shortLivedJWT}`);
            })
            .then((res) => {
                // data from the BE will have newlines which informs indentation in the frontend
                setContent(convert.toHtml(res.data));
            })
            .catch((err) => {
                console.error(err);
            });
    }, [session?._id, config.apihost, path]);

    return (
        <pre
            className="m-0 overflow-auto p-[10px] rounded-[5px]"
            style={{
                backgroundColor: '#333',
                color: 'white',
                maxHeight,
                height: maxHeight,
            }}
            dangerouslySetInnerHTML={{ __html: content }}
        />
    );
};

export default ShowFile;
