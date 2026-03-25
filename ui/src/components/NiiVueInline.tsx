import React, { useEffect, useRef } from 'react';
// @ts-ignore
import { Niivue } from '@niivue/niivue';
import axios from '../axios.instance';
import { useAppSelector } from '../store/hooks';

interface NiiVueInlineProps {
    path: string;
    height?: number;
}

/**
 * Inline NiiVue viewer that renders a NIfTI volume directly in the page.
 * Unlike NiiVueViewer (modal), this embeds at the point of use.
 */
const NiiVueInline: React.FC<NiiVueInlineProps> = ({ path, height = 250 }) => {
    const session = useAppSelector((state) => state.session.data);
    const config = useAppSelector((state) => state.session.config);
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const nvRef = useRef<any>(null);

    useEffect(() => {
        if (!canvasRef.current || !path || !session?._id) return;

        // Clean up previous instance
        if (nvRef.current) {
            try {
                nvRef.current.closeDrawing();
            } catch {
                // ignore cleanup errors
            }
            nvRef.current = null;
        }

        const nv = new Niivue({
            dragAndDropEnabled: false,
            backColor: [0, 0, 0, 1],
        });
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

        return () => {
            if (nvRef.current) {
                try {
                    nvRef.current.closeDrawing();
                } catch {
                    // ignore
                }
                nvRef.current = null;
            }
        };
    }, [path, session?._id, config.apihost]);

    return <canvas ref={canvasRef} className="w-full rounded" height={height} />;
};

export default NiiVueInline;
