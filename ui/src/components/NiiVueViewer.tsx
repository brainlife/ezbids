import React, { useEffect, useRef, useState, useCallback } from 'react';
// @ts-ignore
import { Niivue } from '@niivue/niivue';
import axios from '../axios.instance';
import { useAppSelector } from '../store/hooks';

interface NiiVueViewerProps {
    path: string | null;
    onClose: () => void;
}

const NiiVueViewer: React.FC<NiiVueViewerProps> = ({ path, onClose }) => {
    const session = useAppSelector((state) => state.session.data);
    const config = useAppSelector((state) => state.session.config);
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const [open, setOpen] = useState(false);
    const nvRef = useRef<any>(null);

    const load = useCallback(() => {
        if (!path || !session?._id) return;

        axios.get(`${config.apihost}/download/${session._id}/token`).then((res) => {
            const url = `${config.apihost}/download/${session._id}/${path}?token=${res.data}`;
            setOpen(true);
        });
    }, [path, session?._id, config.apihost]);

    // When path changes, trigger load
    useEffect(() => {
        if (path) load();
    }, [path, load]);

    // When dialog opens and canvas is available, attach NiiVue
    useEffect(() => {
        if (!open || !canvasRef.current || !path || !session?._id) return;

        const nv = new Niivue({ dragAndDropEnabled: false });
        nvRef.current = nv;

        axios.get(`${config.apihost}/download/${session._id}/token`).then((res) => {
            const url = `${config.apihost}/download/${session._id}/${path}?token=${res.data}`;
            nv.attachToCanvas(canvasRef.current);
            nv.loadVolumes([
                {
                    url,
                    volume: { hdr: null, img: null },
                    colorMap: 'gray',
                    opacity: 1,
                    visible: true,
                },
            ]);
        });
    }, [open, path, session?._id, config.apihost]);

    const handleClose = () => {
        setOpen(false);
        onClose();
    };

    if (!open) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
            <div className="bg-white rounded-lg shadow-xl w-[70%] max-w-4xl">
                <div className="flex items-center justify-between p-4 border-b">
                    <h3 className="text-lg font-medium">{path}</h3>
                    <button className="text-gray-400 hover:text-gray-600 text-2xl leading-none" onClick={handleClose}>
                        &times;
                    </button>
                </div>
                <div className="p-4">
                    <canvas ref={canvasRef} className="w-full" height={500} />
                </div>
            </div>
        </div>
    );
};

export default NiiVueViewer;
