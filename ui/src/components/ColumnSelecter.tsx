import React from 'react';

interface ColumnSelecterProps {
    value: string;
    onChange: (value: string) => void;
    columnKeys: string[];
    sampleValues: Record<string, string[]>;
}

const ColumnSelecter: React.FC<ColumnSelecterProps> = ({ value, onChange, columnKeys, sampleValues }) => {
    const composeSampleValue = (key: string) => {
        const samples = sampleValues[key].join(', ');
        if (samples.length > 30) return samples.substring(0, 30) + ' ...';
        return samples;
    };

    return (
        <select
            className="text-sm border border-gray-300 rounded px-2 py-1"
            value={value}
            onChange={(e) => onChange(e.target.value)}
        >
            <option value="">Select column</option>
            {columnKeys.map((key, idx) => (
                <option key={idx} value={key}>
                    {key} — {composeSampleValue(key)}
                </option>
            ))}
        </select>
    );
};

export default ColumnSelecter;
