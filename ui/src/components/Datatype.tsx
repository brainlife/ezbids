import React, { useMemo } from 'react';
import { useAppSelector } from '../store/hooks';

interface DatatypeProps {
    type: string;
    series_idx: number;
    entities: Record<string, string>;
}

const Datatype: React.FC<DatatypeProps> = ({ type, series_idx, entities }) => {
    const ezbidsData = useAppSelector((state) => state.ezbids.data);

    const sessionEntities = useMemo(() => {
        const ents: Record<string, string> = {};

        // set with series default first
        const series = ezbidsData?.series?.[series_idx];
        if (series) {
            for (const key in series.entities) {
                if (series.entities[key] === '') continue;
                ents[key] = series.entities[key];
            }
        }

        // then add overrides
        for (const key in entities) {
            if (key === 'subject') continue;
            if (key === 'session') continue;
            if (entities[key] === '') continue;
            ents[key] = entities[key];
        }
        return ents;
    }, [ezbidsData, series_idx, entities]);

    const color = useMemo(() => {
        const hash = type.split('').reduce((a: number, b: string) => {
            a = (a << 5) - a + b.charCodeAt(0);
            return a & a;
        }, 0);
        const numhash = Math.abs(hash + 12) % 360;
        return `hsl(${numhash % 360}, 50%, 55%)`;
    }, [type]);

    return (
        <div className="inline text-[90%]">
            <span className="inline-block w-2 h-2 rounded-full relative top-[3px]" style={{ backgroundColor: color }}>
                &nbsp;
            </span>{' '}
            {type}
            {Object.entries(sessionEntities).map(([k, v]) => (
                <span
                    key={k}
                    className="inline-block border border-gray-300 rounded text-xs px-1 mr-[3px] text-gray-500"
                >
                    <small>{k}-</small>
                    <b>{v}</b>
                </span>
            ))}
        </div>
    );
};

export default Datatype;
