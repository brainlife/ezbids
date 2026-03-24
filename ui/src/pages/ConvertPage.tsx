import { useEffect, useCallback, useState, useRef } from 'react';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import toast from 'react-hot-toast';

import { useAppSelector, useAppDispatch } from '../store/hooks';
import { setPage, type PageName } from '../store/slices/pageSlice';
import { resetSession, loadSession } from '../store/slices/sessionSlice';
import {
    resetEzbids,
    loadEzbids,
    loadDefaceStatus,
    organizeObjects,
    selectBIDSEntities,
    selectFindSubject,
    selectFindSession,
    type IObject,
} from '../store/slices/ezbidsSlice';
import { resetEvents, updateEvents } from '../store/slices/eventsSlice';
import { hasAuth, createEventsTSV } from '../lib';
import { setSectionIDs, funcQA, fmapQA, dwiQA, petQA, setRun, setVolumeThreshold, setIntendedFor } from '../libUnsafe';

import Upload from './convert/Upload';
import Description from './convert/Description';
import Subject from './convert/Subject';
import Participant from './convert/Participant';
import SeriesPage from './convert/SeriesPage';
import Events from './convert/Events';
import Objects from './convert/Objects';
import Deface from './convert/Deface';
import Finalize from './convert/Finalize';
import Feedback from './convert/Feedback';
import NiiVueViewer from '../components/NiiVueViewer';
import WorkflowDialog from '../components/WorkflowDialog';
import ManageUsersDialog from '../components/dialogs/ManageUsersDialog';

import blLogo from '../assets/bl_logo.png';

const PAGES: PageName[] = [
    'upload',
    'description',
    'subject',
    'seriespage',
    'event',
    'object',
    'deface',
    'participant',
    'finalize',
    'feedback',
];

const PAGE_LABELS: Record<PageName, string> = {
    upload: 'Upload Imaging Data',
    description: 'Dataset Description',
    subject: 'Subjects/Sessions',
    seriespage: 'Series Mapping',
    event: 'Events',
    object: 'Dataset Review',
    deface: 'Deface',
    participant: 'Participants Info',
    finalize: 'Access BIDS Data',
    feedback: 'Feedback',
};

export default function ConvertPage() {
    const dispatch = useAppDispatch();
    const page = useAppSelector((s) => s.page.current);
    const session = useAppSelector((s) => s.session.data);
    const config = useAppSelector((s) => s.session.config);
    const ezbids = useAppSelector((s) => s.ezbids.data);
    const getBIDSEntities = useAppSelector(selectBIDSEntities);
    const findSubject = useAppSelector(selectFindSubject);
    const findSession = useAppSelector(selectFindSession);
    const [niivuePath, setNiivuePath] = useState<string | undefined>();

    // Refs for page components (for isValid callbacks)
    const pageRef = useRef<any>(null);

    // Map object entities from parent series/subject
    const mapObject = useCallback(
        (o: IObject) => {
            const series = ezbids.series[o.series_idx];
            if (series) {
                o._SeriesDescription = series.SeriesDescription.replace('_RR', '');
                o._type = series.type;
            }
            if (o.type) o._type = o.type;

            const e: any = Object.assign({}, getBIDSEntities(o._type));
            for (const k in e) {
                if (series) e[k] = series.entities[k];
                else e[k] = '';
            }
            for (const k in o.entities) {
                if (o.entities[k]) e[k] = o.entities[k];
            }

            o._exclude = o.exclude;
            if (o._type === 'exclude') o._exclude = true;

            const subject = findSubject(o);
            if (subject?.exclude) o._exclude = true;
            if (!o.entities.subject && subject) {
                (e as any).subject = subject.subject;
            }

            const sess = subject ? findSession(subject, o) : undefined;
            if (sess?.exclude) o._exclude = true;
            if (!o.entities.session && sess) {
                (e as any).session = sess.session;
            }

            o._entities = e;
        },
        [ezbids.series, getBIDSEntities, findSubject, findSession]
    );

    const mapObjects = useCallback(() => {
        ezbids.objects.forEach(mapObject);
    }, [ezbids.objects, mapObject]);

    // Init: reset and load from hash
    useEffect(() => {
        dispatch(resetSession());
        dispatch(resetEzbids());
        dispatch(resetEvents());
        dispatch(setPage('upload'));

        // In HashRouter (Electron), location.hash is used for routing (e.g. #/convert),
        // not session IDs. Only treat hash as session ID if it looks like a MongoDB ObjectId
        // or UUID (not a route path).
        const rawHash = location.hash.substring(1); // remove #
        const sessionId = rawHash && !rawHash.startsWith('/') ? rawHash : null;

        if (sessionId) {
            const id = sessionId;
            // Reload sequence — simplified async dispatch chain
            dispatch({ type: 'session/setSession', payload: { _id: id } } as any);
            dispatch(loadSession()).then(() => {
                dispatch(loadEzbids()).then(() => {
                    // mapObjects + organize after data loads
                    setTimeout(() => {
                        mapObjects();
                        dispatch(organizeObjects());
                        dispatch(loadDefaceStatus());
                    }, 100);
                });
            });
        }
    }, []);

    // Polling
    useEffect(() => {
        const interval = setInterval(async () => {
            if (!session) return;
            const status = session.status;
            if (status !== 'analyzed' && status !== 'finished') {
                if (status === 'defacing') {
                    dispatch(loadDefaceStatus());
                }
                dispatch(loadSession());
            }
            if (ezbids.notLoaded) {
                dispatch(loadEzbids());
            }
        }, 5000);
        return () => clearInterval(interval);
    }, [session, ezbids.notLoaded, dispatch]);

    // Navigation
    const backLabel = page === 'upload' ? (session ? 'Re-Upload' : null) : 'Back';
    const backButtonType = page === 'upload' ? 'warning' : 'info';
    const nextLabel =
        page === 'upload'
            ? session && session.pre_finish_date && !ezbids.notLoaded
                ? 'Next'
                : null
            : page === 'feedback'
            ? null
            : 'Next';

    const handleNext = useCallback(() => {
        mapObjects();
        dispatch(organizeObjects());

        const ref = pageRef.current;
        if (ref && ref.isValid) {
            ref.isValid((err: string | null) => {
                if (err) {
                    toast.error(err);
                } else {
                    const idx = PAGES.indexOf(page);
                    dispatch(setPage(PAGES[idx + 1]));

                    // Post-navigation processing
                    switch (PAGES[idx + 1]) {
                        case 'event':
                            petQA(ezbids);
                            break;
                        case 'object':
                            setVolumeThreshold(ezbids);
                            setSectionIDs(ezbids);
                            funcQA(ezbids);
                            fmapQA(ezbids);
                            dwiQA(ezbids);
                            setRun(ezbids);
                            setIntendedFor(ezbids);
                            mapObjects();
                            break;
                        case 'deface':
                            createEventsTSV(ezbids, ezbids as any);
                            break;
                    }
                    window.scrollTo(0, 0);
                }
            });
        } else {
            // No validation — just advance
            const idx = PAGES.indexOf(page);
            dispatch(setPage(PAGES[idx + 1]));
            window.scrollTo(0, 0);
        }
    }, [page, ezbids, mapObjects, dispatch]);

    const handleBack = useCallback(() => {
        const idx = PAGES.indexOf(page);
        if (idx === 0) {
            if (confirm('Do you really want to start over?')) {
                document.location.hash = '';
                document.location.reload();
            }
        } else {
            dispatch(setPage(PAGES[idx - 1]));
        }
    }, [page, dispatch]);

    const handleSignout = () => {
        document.location.href = config.authSignOut;
    };

    const renderPage = () => {
        const props = { ref: pageRef };
        switch (page) {
            case 'upload':
                return <Upload {...props} />;
            case 'description':
                return <Description {...props} />;
            case 'subject':
                return <Subject {...props} />;
            case 'participant':
                return <Participant {...props} />;
            case 'seriespage':
                return <SeriesPage {...props} onNiivue={setNiivuePath} />;
            case 'event':
                return <Events {...props} onMapObjects={mapObjects} />;
            case 'object':
                return (
                    <Objects
                        {...props}
                        onNiivue={setNiivuePath}
                        onMapObjects={mapObjects}
                        onUpdateObject={(o: IObject) => {
                            mapObject(o);
                            dispatch(organizeObjects());
                        }}
                    />
                );
            case 'deface':
                return <Deface {...props} onNiivue={setNiivuePath} />;
            case 'finalize':
                return <Finalize {...props} />;
            case 'feedback':
                return <Feedback {...props} />;
            default:
                return null;
        }
    };

    const sidebarItem = (p: PageName, indent = false) => (
        <li
            key={p}
            className={`px-2.5 py-2.5 ${indent ? 'list-disc list-inside' : ''} ${
                page === p ? 'bg-green-500 text-white' : 'text-white'
            }`}
        >
            {PAGE_LABELS[p]}
        </li>
    );

    return (
        <div>
            {/* Sidebar */}
            <aside
                className="fixed w-40 top-0 left-0 h-full text-white"
                style={{
                    background:
                        'linear-gradient(rgb(70,188,152), rgb(53,150,121), rgb(45,113,141), rgb(31,82,95), rgb(16,45,71))',
                }}
            >
                <h1 className="p-2.5 m-0 text-[25pt]">
                    <span className="tracking-[-3px] opacity-60">ez</span>BIDS
                </h1>

                <ul className="list-none pl-0 m-0">
                    {sidebarItem('upload')}
                    {sidebarItem('description')}
                </ul>

                <div className="mb-2.5">
                    <h2 className="mb-0 p-2.5 text-[110%] text-white opacity-50 font-bold bg-black/5">
                        Dataset Mappings
                    </h2>
                    <ul className="list-none pl-0 m-0">
                        {sidebarItem('subject', true)}
                        {sidebarItem('seriespage', true)}
                        {sidebarItem('event', true)}
                    </ul>
                </div>

                <ul className="list-none pl-0 m-0">{sidebarItem('object')}</ul>

                <div className="mb-2.5">
                    <h2 className="mb-0 p-2.5 text-[110%] text-white opacity-50 font-bold bg-black/5">Optional</h2>
                    <ul className="list-none pl-0 m-0">
                        {sidebarItem('deface', true)}
                        {sidebarItem('participant', true)}
                    </ul>
                </div>

                <ul className="list-none pl-0 m-0">
                    {sidebarItem('finalize')}
                    {sidebarItem('feedback')}
                </ul>

                {/* Footer links */}
                <div className="p-3.5 flex justify-between">
                    <a
                        href="https://brainlife.io"
                        target="_blank"
                        rel="noreferrer"
                        className="flex"
                        title="Open brainlife"
                    >
                        <img src={blLogo} className="w-8 h-8" alt="brainlife logo" />
                    </a>
                    <a href="https://github.com/brainlife/ezbids" target="github" title="Open github">
                        <FontAwesomeIcon icon={['fab', 'github']} className="text-white w-8 h-8 hover:text-gray-300" />
                    </a>
                    <a
                        href="https://brainlife.io/docs/using_ezBIDS/"
                        target="_blank"
                        rel="noreferrer"
                        title="Open documentation"
                    >
                        <FontAwesomeIcon icon="book" className="text-white w-8 h-8 hover:text-gray-300" />
                    </a>
                </div>

                <div className="px-2.5 mb-2">
                    <WorkflowDialog />
                </div>

                {hasAuth() && <ManageUsersDialog />}

                <div className="w-[135px] px-2.5">
                    <button
                        className="w-full py-1.5 border border-gray-300 rounded bg-white text-black font-inherit"
                        onClick={handleSignout}
                    >
                        Signout
                    </button>
                </div>
            </aside>

            {/* Main content */}
            <section className="ml-40 pb-24">
                {renderPage()}

                {session && (
                    <div className="fixed bottom-0 right-0 left-40 h-10 p-2.5 bg-black/20 z-[3] flex justify-between items-center">
                        {backLabel ? (
                            <button
                                className={`px-4 py-1.5 rounded text-white ${
                                    backButtonType === 'warning'
                                        ? 'bg-orange-500 hover:bg-orange-600'
                                        : 'bg-blue-400 hover:bg-blue-500'
                                }`}
                                onClick={handleBack}
                            >
                                <FontAwesomeIcon icon="angle-left" className="mr-1" />
                                {backLabel}
                            </button>
                        ) : (
                            <div />
                        )}
                        {nextLabel && (
                            <button
                                className="px-4 py-1.5 rounded bg-blue-600 hover:bg-blue-700 text-white"
                                onClick={handleNext}
                            >
                                {nextLabel}
                                <FontAwesomeIcon icon="angle-right" className="ml-1" />
                            </button>
                        )}
                    </div>
                )}
            </section>

            {niivuePath && <NiiVueViewer path={niivuePath} onClose={() => setNiivuePath(undefined)} />}
        </div>
    );
}
