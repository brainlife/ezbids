import React, { useEffect, useState } from 'react';
import axios from '../axios.instance';
import { useAppSelector } from '../store/hooks';

const AnalysisErrors: React.FC = () => {
    const session = useAppSelector((state) => state.session.data);
    const config = useAppSelector((state) => state.session.config);
    const [errors, setErrors] = useState('');

    useEffect(() => {
        if (!session?._id) return;

        const fetchErrors = async () => {
            try {
                const jwt = await axios.get(`${config.apihost}/download/${session._id}/token`);
                const res = await axios.get(
                    `${config.apihost}/download/${session._id}/dcm2niix_error?token=${jwt.data}`
                );
                if (res.status === 200) {
                    setErrors(res.data);
                } else {
                    setErrors('Failed to load dcm2niix error log');
                }
            } catch {
                // 404 is expected when no dcm2niix errors exist — silently ignore
            }
        };

        fetchErrors();
    }, [session?._id, config.apihost]);

    if (!errors) return null;

    return (
        <div
            className="border-[3px] border-red-600 p-[10px] rounded-[5px] text-red-600"
            style={{ backgroundColor: '#fee' }}
        >
            <h3>dcm2niix Errors</h3>
            <p className="mb-[10px]">
                We encountered a dcm2niix error (or errors) that may require attention. If this should be addressed,
                please submit an issue at{' '}
                <a href="https://github.com/rordenlab/dcm2niix/issues" target="rordenlab/dcm2niix">
                    https://github.com/rordenlab/dcm2niix/issues
                </a>
                . Copy the information below for each unique error message (beginning with the &quot;+&quot; key) and
                paste into in the body of your dcm2niix issue, if you choose to submit an issue. You can send your error
                DICOM files/folders to the dcm2niix team via a shared Google Drive folder.
            </p>
            <pre
                className="overflow-auto p-[10px] mt-0 mb-[5px] -mx-[10px]"
                style={{
                    backgroundColor: '#333',
                    color: 'white',
                    maxHeight: '300px',
                }}
            >
                {errors}
            </pre>
            <p>You may continue ezBIDS with the other successfully converted data if you wish.</p>
        </div>
    );
};

export default AnalysisErrors;
