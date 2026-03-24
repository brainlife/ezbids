import { forwardRef, useCallback, useEffect, useImperativeHandle, useState } from 'react';
import { useAppSelector, useAppDispatch } from '../../store/hooks';
import { updateEzbids, type Subject as SubjectType, type Session } from '../../store/slices/ezbidsSlice';

interface SubjectHandle {
    isValid: (cb: (err?: string) => void) => void;
}

const Subject = forwardRef<SubjectHandle>(function Subject(_props, ref) {
    const ezbids = useAppSelector((s) => s.ezbids.data);
    const [, forceUpdate] = useState(0);

    const validate = useCallback((s: SubjectType) => {
        s.validationErrors = [];
        if (s.subject.length === 0) {
            s.validationErrors.push('subject is a required field');
        }
        const cleansub = s.subject.replace(/[^0-9a-zA-Z]/g, '');
        if (s.subject !== cleansub) {
            s.validationErrors.push('subject contains non alphanumeric characters');
        }
    }, []);

    const validateAll = useCallback(() => {
        ezbids.subjects.forEach(validate);
    }, [ezbids.subjects, validate]);

    useEffect(() => {
        console.log('Subject create');
        validateAll();
        forceUpdate((n) => n + 1);
    }, []);

    useImperativeHandle(
        ref,
        () => ({
            isValid(cb: (err?: string) => void) {
                validateAll();
                let err: string | undefined;
                ezbids.subjects.forEach((s: SubjectType) => {
                    if (s.validationErrors.length > 0) err = 'Please correct all issues';
                });
                forceUpdate((n) => n + 1);
                return cb(err);
            },
        }),
        [ezbids.subjects, validateAll]
    );

    const [dropdownOpen, setDropdownOpen] = useState(false);

    const resetSubjects = useCallback(
        (command: string) => {
            console.log('resetting subjects');
            let sub = 1;
            switch (command) {
                case 'num':
                    ezbids.subjects.forEach((s: SubjectType) => {
                        s.subject = sub.toString().padStart(2, '0');
                        sub++;
                    });
                    break;
                case 'pid':
                    ezbids.subjects.forEach((s: SubjectType) => {
                        const firstInfo = s.PatientInfo[0];
                        s.subject = firstInfo.PatientID.replace(/[^0-9a-zA-Z]/g, '');
                    });
                    break;
                case 'pname':
                    ezbids.subjects.forEach((s: SubjectType) => {
                        const firstInfo = s.PatientInfo[0];
                        s.subject = firstInfo.PatientName.replace(/[^0-9a-zA-Z]/g, '');
                    });
                    break;
            }
            validateAll();
            setDropdownOpen(false);
            forceUpdate((n) => n + 1);
        },
        [ezbids.subjects, validateAll]
    );

    const handleSubjectChange = useCallback(
        (subject: SubjectType, value: string) => {
            subject.subject = value.trim();
            validate(subject);
            forceUpdate((n) => n + 1);
        },
        [validate]
    );

    const handleSessionChange = useCallback(
        (subject: SubjectType, session: Session, value: string) => {
            session.session = value.trim();
            validate(subject);
            forceUpdate((n) => n + 1);
        },
        [validate]
    );

    const handleExcludeSubject = useCallback((subject: SubjectType, checked: boolean) => {
        subject.exclude = checked;
        forceUpdate((n) => n + 1);
    }, []);

    const handleExcludeSession = useCallback((session: Session, checked: boolean) => {
        session.exclude = checked;
        forceUpdate((n) => n + 1);
    }, []);

    return (
        <div className="p-5">
            <p>
                Please map DICOM subject ID to BIDS subject ID. You can also specify session (AcquisitionDate) mappings
                for each subject, if appropriate. A mapping table can be downloaded at the end for future reference.
            </p>

            {/* Reset Subject Mapping Dropdown */}
            <div className="float-right m-2.5 relative">
                <button
                    className="px-3 py-1.5 bg-blue-500 hover:bg-blue-600 text-white text-sm rounded"
                    onClick={() => setDropdownOpen(!dropdownOpen)}
                >
                    Reset Subject Mapping <span className="ml-1">&#9662;</span>
                </button>
                {dropdownOpen && (
                    <ul className="absolute right-0 mt-1 bg-white border border-gray-200 rounded shadow-lg z-10 min-w-[180px] list-none p-0 m-0">
                        <li
                            className="px-4 py-2 hover:bg-gray-100 cursor-pointer text-sm"
                            onClick={() => resetSubjects('pname')}
                        >
                            Use PatientName
                        </li>
                        <li
                            className="px-4 py-2 hover:bg-gray-100 cursor-pointer text-sm"
                            onClick={() => resetSubjects('pid')}
                        >
                            Use PatientID
                        </li>
                        <li
                            className="px-4 py-2 hover:bg-gray-100 cursor-pointer text-sm"
                            onClick={() => resetSubjects('num')}
                        >
                            Numerical (1,2,3..)
                        </li>
                    </ul>
                )}
            </div>

            {/* Subjects Table */}
            <table className="w-full text-sm align-top border-collapse">
                <thead>
                    <tr className="bg-gray-50">
                        <th className="p-2 text-left w-[330px] border-b border-gray-200">DICOM Patient</th>
                        <th className="p-2 text-left border-b border-gray-200">Subject/Sessions Mappings</th>
                    </tr>
                </thead>
                <tbody>
                    {ezbids.subjects.map((subject, sIdx) => (
                        <tr key={sIdx} className="border-b border-gray-200 align-top">
                            {/* DICOM Patient Column */}
                            <td className="p-2 w-[330px]">
                                <span className="float-right text-xl font-bold">&rarr;</span>
                                <div>
                                    {subject.PatientInfo.map((info, infoIdx) => (
                                        <p
                                            key={infoIdx}
                                            className={`mt-0 mb-1 ${infoIdx > 0 ? 'border-t border-black/5 pt-1' : ''}`}
                                        >
                                            <b>PatientID</b> {info.PatientID}
                                            <br />
                                            <b>PatientName</b> {info.PatientName}
                                            <br />
                                            <b>PatientBirthDate</b> {info.PatientBirthDate || '(not set)'}
                                            <br />
                                            <b>Directory</b> {(info as any).file_directory}
                                            <br />
                                        </p>
                                    ))}
                                </div>
                            </td>

                            {/* Subject/Sessions Mappings Column */}
                            <td className="p-2">
                                <label className="flex items-center gap-1 mb-2 cursor-pointer">
                                    <input
                                        type="checkbox"
                                        checked={subject.exclude}
                                        onChange={(e) => handleExcludeSubject(subject, e.target.checked)}
                                        title="Exclude all objects from BIDS output for this subject"
                                    />
                                    Exclude this subject
                                </label>

                                <div className="flex items-center mb-2">
                                    <span className="bg-gray-100 border border-gray-300 border-r-0 px-2 py-1 text-sm rounded-l">
                                        sub-
                                    </span>
                                    <input
                                        type="text"
                                        className="border border-gray-300 px-2 py-1 text-sm rounded-r flex-1"
                                        value={subject.subject}
                                        onChange={(e) => handleSubjectChange(subject, e.target.value)}
                                    />
                                </div>

                                {/* Sessions Sub-Table */}
                                {subject.sessions.length > 0 && (
                                    <table className="w-full text-sm mb-2">
                                        <tbody>
                                            {subject.sessions.map((session, sesIdx) => (
                                                <tr key={sesIdx}>
                                                    <td className="p-1 w-1/3 align-top">
                                                        <b>AcquisitionDate</b>
                                                        <br />
                                                        {session.AcquisitionDate}
                                                    </td>
                                                    <td className="p-1 w-2/3">
                                                        <label className="flex items-center gap-1 mb-1 cursor-pointer">
                                                            <input
                                                                type="checkbox"
                                                                checked={session.exclude}
                                                                onChange={(e) =>
                                                                    handleExcludeSession(session, e.target.checked)
                                                                }
                                                                title="Exclude all objects for this session"
                                                            />
                                                            Exclude this session
                                                        </label>
                                                        <div className="flex items-center">
                                                            <span className="bg-gray-100 border border-gray-300 border-r-0 px-2 py-1 text-sm rounded-l">
                                                                ses-
                                                            </span>
                                                            <input
                                                                type="text"
                                                                className="border border-gray-300 px-2 py-1 text-sm rounded-r flex-1"
                                                                placeholder="no session"
                                                                value={session.session}
                                                                onChange={(e) =>
                                                                    handleSessionChange(
                                                                        subject,
                                                                        session,
                                                                        e.target.value
                                                                    )
                                                                }
                                                            />
                                                        </div>
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                )}

                                {/* Validation Errors */}
                                {subject.validationErrors.map((error, errIdx) => (
                                    <div
                                        key={errIdx}
                                        className="flex items-center gap-2 p-2 mb-1 bg-red-50 border border-red-200 rounded text-red-700 text-sm"
                                    >
                                        <span className="text-red-500">&#9888;</span>
                                        {error}
                                    </div>
                                ))}
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>

            <pre className="mt-4 text-xs bg-gray-50 p-2 rounded overflow-auto">
                {JSON.stringify(ezbids.subjects, null, 2)}
            </pre>
        </div>
    );
});

export default Subject;
