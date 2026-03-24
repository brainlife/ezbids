import { useNavigate } from 'react-router-dom';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faCircleCheck, faArrowUpRightFromSquare } from '@fortawesome/free-solid-svg-icons';
import { hasJWT, hasAuth } from '../../lib';
import { useAppSelector } from '../../store/hooks';
import Animation from './Animation';

const featureCards = [
    'No installation or programming requirements',
    'Handles both metadata as well as imaging/task events data',
    'Semi-automated inference and guidance for adherence to BIDS',
];

export default function Content() {
    const navigate = useNavigate();
    const config = useAppSelector((s) => s.session.config);

    function openDocumentation() {
        window.open('https://brainlife.io/docs/using_ezBIDS/');
    }

    function onClickGetStarted() {
        if (!hasAuth() || hasJWT()) {
            navigate('/convert');
            return;
        }

        sessionStorage.setItem('auth_redirect', `${window.location.href}convert`);
        window.location.href = config.authSignIn;
    }

    return (
        <main className="p-0 flex-1">
            {/* Hero banner */}
            <div className="flex flex-col-reverse md:flex-row items-center h-auto md:h-[calc(90vh-62px-35vh)]">
                <div className="hidden md:block md:w-[4%]" />
                <div className="w-full md:w-[42%] p-5">
                    <h1 className="text-xl md:text-2xl xl:text-3xl font-bold my-2.5">
                        Convert neuroimaging data and associated metadata to the BIDS standard
                    </h1>
                    <p className="text-base md:text-lg xl:text-xl my-2.5 leading-relaxed">
                        ezBIDS requires neither coding proficiency nor knowledge of BIDS in order to get started. It is
                        the first BIDS tool to offer guided standardization, support for task events conversion, and
                        interoperability with{' '}
                        <a
                            href="https://openneuro.org"
                            className="text-[#3782e5] no-underline hover:underline hover:opacity-80 inline"
                            target="_blank"
                            rel="noreferrer"
                        >
                            OpenNeuro
                        </a>{' '}
                        and{' '}
                        <a
                            href="https://brainlife.io"
                            className="text-[#3782e5] no-underline hover:underline hover:opacity-80 inline"
                            target="_blank"
                            rel="noreferrer"
                        >
                            brainlife.io
                        </a>
                        . Our recent publication in <i>Scientific Data</i> can be found{' '}
                        <a
                            href="https://www.nature.com/articles/s41597-024-02959-0"
                            className="text-[#3782e5] no-underline hover:underline hover:opacity-80 inline"
                            target="_blank"
                            rel="noreferrer"
                        >
                            here
                        </a>
                        .
                    </p>
                    <div className="flex flex-col md:flex-row gap-2 mt-2">
                        <button
                            onClick={onClickGetStarted}
                            className="bg-blue-500 text-white font-bold py-2.5 px-6 rounded hover:bg-blue-600 transition-colors w-full md:w-1/2 h-[50px] md:h-[40px] text-base cursor-pointer"
                        >
                            GET STARTED
                        </button>
                        <button
                            onClick={openDocumentation}
                            className="text-[#3782e5] py-2.5 px-6 rounded hover:bg-gray-50 transition-colors w-full md:w-1/2 h-[50px] md:h-[40px] text-base cursor-pointer"
                        >
                            <FontAwesomeIcon icon={faArrowUpRightFromSquare} className="mr-1" />
                            See documentation
                        </button>
                    </div>
                </div>
                <div className="hidden md:block md:w-[4%]" />
                <div className="w-full md:w-[50%] p-5">
                    <Animation />
                </div>
            </div>

            {/* Feature cards */}
            <div className="flex flex-col md:flex-row items-center bg-[#20ab5c] min-h-[35vh]">
                {featureCards.map((text, i) => (
                    <div key={i} className="w-full md:w-1/4 p-4 md:p-6 xl:p-8 h-full">
                        <div className="bg-white rounded shadow p-6 h-full flex flex-row md:flex-col items-center text-center">
                            <FontAwesomeIcon
                                icon={faCircleCheck}
                                className="text-[#20ab5c] text-3xl w-10 h-10 mr-5 md:mr-0 md:mb-4 flex-shrink-0"
                            />
                            <span>{text}</span>
                        </div>
                    </div>
                ))}
                <div className="w-full md:w-1/4 p-4 md:p-6 xl:p-8 h-full">
                    <div className="bg-white rounded shadow p-6 h-full flex flex-row md:flex-col items-center text-center">
                        <FontAwesomeIcon
                            icon={faCircleCheck}
                            className="text-[#20ab5c] text-3xl w-10 h-10 mr-5 md:mr-0 md:mb-4 flex-shrink-0"
                        />
                        <span>
                            Multiple data management options: download BIDS data to local system, or transfer to either{' '}
                            <a
                                href="https://openneuro.org"
                                className="text-[#3782e5] no-underline hover:underline hover:opacity-80 inline"
                                target="_blank"
                                rel="noreferrer"
                            >
                                OpenNeuro
                            </a>{' '}
                            or{' '}
                            <a
                                href="https://brainlife.io"
                                className="text-[#3782e5] no-underline hover:underline hover:opacity-80 inline"
                                target="_blank"
                                rel="noreferrer"
                            >
                                brainlife.io
                            </a>
                            .
                        </span>
                    </div>
                </div>
            </div>
        </main>
    );
}
