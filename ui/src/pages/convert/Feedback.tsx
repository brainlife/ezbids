import { forwardRef, useCallback, useImperativeHandle } from 'react';

import danLevitas from '../../assets/images/DanLevitas.png';
import franco from '../../assets/images/franco.jpg';
import soichi from '../../assets/images/soichi.jpg';
import anibal from '../../assets/images/Anibal.png';
import dheeraj from '../../assets/images/DheerajBhatia.png';
import nick from '../../assets/images/NickLee.jpeg';

interface FeedbackHandle {
    isValid: (cb: (err?: string) => void) => void;
}

const teamMembers = [
    { name: 'Dan Levitas', email: 'dlevitas@iu.edu', role: 'Software Engineer', img: danLevitas },
    { name: 'Franco Pestilli', email: 'pestilli@utexas.edu', role: 'Associate Professor', img: franco },
    { name: 'Soichi Hayashi', email: 'hayashis@iu.edu', role: 'Technical Lead', img: soichi },
    { name: 'Anibal S. Heinsfeld', email: 'anibalsolon@utexas.edu', role: 'Software Engineer', img: anibal },
    { name: 'Dheeraj Bhatia', email: 'dheeraj.bhatia@austin.utexas.edu', role: 'Software Engineer', img: dheeraj },
    { name: 'Nick Lee', email: 'niconal902@gmail.com', role: 'Software Engineer', img: nick },
];

const Feedback = forwardRef<FeedbackHandle>(function Feedback(_props, ref) {
    const restart = useCallback(() => {
        document.location.hash = '';
        document.location.reload();
    }, []);

    useImperativeHandle(
        ref,
        () => ({
            isValid(cb: (err?: string) => void) {
                cb();
            },
        }),
        []
    );

    return (
        <div className="p-5">
            <h1 className="text-2xl font-bold mb-4">Thank you for using ezBIDS!</h1>
            <p className="opacity-80">
                You can close this tab now. Or&nbsp;&nbsp;
                <button
                    className="px-3 py-1.5 bg-blue-500 hover:bg-blue-600 text-white text-sm rounded"
                    onClick={restart}
                >
                    Start Over
                </button>
                &nbsp;&nbsp;if you'd like to convert another dataset.
            </p>
            <br />

            <h2 className="text-xl font-bold pb-1 border-b border-black/20 mb-1">Feedbacks / Comments</h2>
            <p className="opacity-80">
                ezBIDS is a brand new web service! Your feedback is extremely valuable to us. Please send us an email at{' '}
                <a href="mailto:pestilli@utexas.edu" target="mail" className="text-blue-400">
                    pestilli@utexas.edu
                </a>{' '}
                describing your experience with any feedbacks / comments / suggestions.
            </p>
            <p className="opacity-80">
                If you have experienced any issues while using ezBIDS, please submit an{' '}
                <a href="https://github.com/brainlife/ezbids/issues" target="github" className="text-blue-400">
                    Github Issues
                </a>
            </p>
            <br />

            <h2 className="text-xl font-bold pb-1 border-b border-black/20 mb-1">Funded By</h2>
            <p className="opacity-80">ezBIDS was made possible by the following funding sources.</p>
            <p className="opacity-80">
                <a href="https://nsf.gov/awardsearch/showAward?AWD_ID=1734853">
                    <img src="https://img.shields.io/badge/NSF_BCS-1734853-blue.svg" alt="NSF BCS 1734853" />
                </a>
                &nbsp;
                <a href="https://nsf.gov/awardsearch/showAward?AWD_ID=1636893">
                    <img src="https://img.shields.io/badge/NSF_BCS-1636893-blue.svg" alt="NSF BCS 1636893" />
                </a>
                &nbsp;
                <a href="https://nsf.gov/awardsearch/showAward?AWD_ID=1916518">
                    <img src="https://img.shields.io/badge/NSF_ACI-1916518-blue.svg" alt="NSF ACI 1916518" />
                </a>
                &nbsp;
                <a href="https://nsf.gov/awardsearch/showAward?AWD_ID=1912270">
                    <img src="https://img.shields.io/badge/NSF_IIS-1912270-blue.svg" alt="NSF IIS 1912270" />
                </a>
                &nbsp;
                <a href="https://grantome.com/grant/NIH/R01-EB029272-01">
                    <img
                        src="https://img.shields.io/badge/NIH_NIBIB-R01EB029272-green.svg"
                        alt="NIH NIBIB R01EB029272"
                    />
                </a>
            </p>
            <br />
            <br />

            <h2 className="text-xl font-bold pb-1 border-b border-black/20 mb-1">ezBIDS Team</h2>
            <div className="flex flex-wrap">
                {teamMembers.map((member) => (
                    <div
                        key={member.email}
                        className="inline-block w-[250px] p-2.5 mb-5 text-center text-[125%] text-black/60"
                    >
                        <img src={member.img} width={200} className="rounded-full mb-5" alt={member.name} />
                        <br />
                        <b>
                            <a href={`mailto:${member.email}`} target="mail" className="text-blue-400">
                                {member.name}
                            </a>
                        </b>
                        <br />
                        {member.role}
                    </div>
                ))}
            </div>
        </div>
    );
});

export default Feedback;
