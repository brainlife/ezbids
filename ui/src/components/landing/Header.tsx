import { useNavigate } from 'react-router-dom';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faArrowUpRightFromSquare } from '@fortawesome/free-solid-svg-icons';
import { hasAuth, hasJWT } from '../../lib';
import { useAppSelector } from '../../store/hooks';

export default function Header() {
    const navigate = useNavigate();
    const config = useAppSelector((s) => s.session.config);

    function openBrainLifeTeamPage() {
        window.open('https://brainlife.io/team/', '_blank');
    }

    function redirectToBrainlifeAuth() {
        if (!hasAuth() || hasJWT()) {
            navigate('/convert');
            return;
        }

        sessionStorage.setItem('auth_redirect', `${window.location.href}convert`);
        window.location.href = config.authSignIn;
    }

    const buttonLabel = !hasAuth() || hasJWT() ? 'GET STARTED' : 'LOG IN / REGISTER';

    return (
        <div className="sticky top-0 z-50">
            <header className="bg-white h-[62px] p-0">
                <div className="flex items-center">
                    <div className="hidden md:block md:w-[4%]" />
                    <div className="w-full md:w-[92%]">
                        <nav className="flex items-center h-[62px] border-b border-transparent">
                            <span className="text-xl text-[#3482e9] px-4 font-medium cursor-default">ezBIDS</span>
                            <div className="flex-grow" />
                            <button
                                onClick={openBrainLifeTeamPage}
                                className="text-[#3482e9] text-sm md:text-xl px-4 py-2 hover:bg-gray-50 transition-colors cursor-pointer"
                            >
                                <FontAwesomeIcon icon={faArrowUpRightFromSquare} className="mr-1" />
                                TEAM
                            </button>
                            <button
                                onClick={redirectToBrainlifeAuth}
                                className="text-[#3482e9] text-sm md:text-xl px-4 py-2 hover:bg-gray-50 transition-colors font-medium cursor-pointer"
                            >
                                {buttonLabel}
                            </button>
                        </nav>
                    </div>
                    <div className="hidden md:block md:w-[4%]" />
                </div>
            </header>
        </div>
    );
}
