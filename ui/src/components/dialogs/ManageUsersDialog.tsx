import { useState, useMemo } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { Cross2Icon } from '@radix-ui/react-icons';
import toast from 'react-hot-toast';
import { jwtDecode } from 'jwt-decode';

import { useAppSelector, useAppDispatch } from '../../store/hooks';
import { updateAllowedUsers } from '../../store/slices/sessionSlice';
import { retrieveJWT } from '../../lib';
import axios from '../../axios.instance';

interface Profile {
    active?: boolean;
    email?: string;
    fullname?: string;
    profile?: { public: { bio?: string; institution?: string } };
    sub?: number;
    username?: string;
    _id: string;
}

export default function ManageUsersDialog() {
    const dispatch = useAppDispatch();
    const session = useAppSelector((s) => s.session.data);
    const config = useAppSelector((s) => s.session.config);

    const [open, setOpen] = useState(false);
    const [profiles, setProfiles] = useState<Profile[]>([]);
    const [userInput, setUserInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [suggestions, setSuggestions] = useState<Profile[]>([]);

    // Only show if user is the session owner
    const isVisible = useMemo(() => {
        if (!session) return false;
        const jwt = retrieveJWT();
        if (!jwt) return false;
        try {
            const decoded: { sub: number } = jwtDecode(jwt);
            return decoded?.sub === session.ownerId;
        } catch {
            return false;
        }
    }, [session]);

    const allowedUserProfiles = useMemo(() => {
        const list = session?.allowedUsers || [];
        return list.map((sub) => profiles.find((p) => p.sub === sub)).filter(Boolean) as Profile[];
    }, [session?.allowedUsers, profiles]);

    if (!isVisible) return null;

    const handleOpen = () => {
        setOpen(true);
        if (profiles.length > 0) return;
        setIsLoading(true);
        axios
            .get<{ count: number; profiles: Profile[] }>(`${config.authhost}/profile/list?limit=6000`)
            .then((res) => {
                setProfiles(res?.data?.profiles ? [...res.data.profiles] : []);
            })
            .catch(console.error)
            .finally(() => setIsLoading(false));
    };

    const handleSearch = (query: string) => {
        setUserInput(query);
        if (!query) {
            setSuggestions([]);
            return;
        }
        const q = query.toLowerCase();
        const alreadyShared = [session?.ownerId, ...(session?.allowedUsers || [])];
        const results = profiles
            .filter((p) => {
                const email = (p.email || '').toLowerCase();
                const name = (p.fullname || '').toLowerCase();
                return email.includes(q) || name.includes(q);
            })
            .filter((p) => p.sub && !alreadyShared.includes(p.sub))
            .slice(0, 20);
        setSuggestions(results);
    };

    const handleSelect = (profile: Profile) => {
        if (!session || !profile.sub) return;
        setUserInput('');
        setSuggestions([]);
        const updatedUsers = [...(session.allowedUsers || []), profile.sub];
        setIsLoading(true);
        axios
            .patch(`${config.apihost}/session/${session._id}`, { allowedUsers: updatedUsers })
            .then(() => dispatch(updateAllowedUsers(updatedUsers)))
            .catch(() => toast.error('Error sharing session'))
            .finally(() => setIsLoading(false));
    };

    const handleRemove = (sub: number) => {
        if (!session) return;
        const updatedUsers = (session.allowedUsers || []).filter((u) => u !== sub);
        setIsLoading(true);
        axios
            .patch(`${config.apihost}/session/${session._id}`, { allowedUsers: updatedUsers })
            .then(() => dispatch(updateAllowedUsers(updatedUsers)))
            .catch(() => toast.error('Error removing user'))
            .finally(() => setIsLoading(false));
    };

    return (
        <div className="px-2.5">
            <div className="relative w-[135px]">
                <button
                    className="w-full py-1.5 mb-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded text-sm"
                    onClick={handleOpen}
                >
                    Share session
                </button>
                {allowedUserProfiles.length > 0 && (
                    <span className="absolute -top-1.5 -right-1.5 bg-red-500 text-white text-xs w-5 h-5 rounded-full flex items-center justify-center">
                        {allowedUserProfiles.length}
                    </span>
                )}
            </div>

            <Dialog.Root open={open} onOpenChange={setOpen}>
                <Dialog.Portal>
                    <Dialog.Overlay className="fixed inset-0 bg-black/40" />
                    <Dialog.Content className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-white rounded-lg shadow-xl w-[500px] max-h-[85vh] overflow-auto p-6">
                        <Dialog.Title className="text-lg font-semibold mb-4">
                            Share session with other users
                        </Dialog.Title>
                        <Dialog.Close className="absolute top-4 right-4">
                            <Cross2Icon />
                        </Dialog.Close>

                        <h3 className="font-semibold mb-0">Sharing with</h3>
                        <p className="text-gray-400 text-sm mb-3">The following users have access to this session</p>

                        {allowedUserProfiles.length === 0 ? (
                            <p className="text-yellow-600 text-sm">No users added</p>
                        ) : (
                            <div className="flex flex-wrap gap-1 mb-4">
                                {allowedUserProfiles.map((user) => (
                                    <span
                                        key={user.sub}
                                        className="inline-flex items-center gap-1 bg-gray-100 border border-gray-200 rounded px-2 py-1 text-sm"
                                    >
                                        {user.fullname || ''} &lt;{user.email}&gt;
                                        <button
                                            className="text-gray-400 hover:text-red-500 ml-1"
                                            onClick={() => user.sub && handleRemove(user.sub)}
                                        >
                                            ×
                                        </button>
                                    </span>
                                ))}
                            </div>
                        )}

                        <h3 className="font-semibold mb-0 mt-4">Find users</h3>
                        <p className="text-gray-400 text-sm mt-1 mb-2">
                            Use the dropdown to search for other brainlife users
                        </p>

                        <div className="relative">
                            <input
                                type="text"
                                className="w-full border border-gray-300 rounded px-3 py-2 text-sm"
                                placeholder="Start typing to see results"
                                value={userInput}
                                onChange={(e) => handleSearch(e.target.value)}
                            />
                            {isLoading && (
                                <span className="absolute right-3 top-2.5 text-gray-400 text-sm animate-spin">⟳</span>
                            )}
                            {suggestions.length > 0 && (
                                <div className="absolute z-10 top-full left-0 right-0 bg-white border border-gray-200 rounded-b shadow-lg max-h-48 overflow-auto">
                                    {suggestions.map((p) => (
                                        <div
                                            key={p._id}
                                            className="px-3 py-2 hover:bg-blue-50 cursor-pointer text-sm"
                                            onClick={() => handleSelect(p)}
                                        >
                                            {p.fullname} &lt;{p.email}&gt;
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>

                        <div className="mt-6 flex justify-end">
                            <button
                                className="px-4 py-2 bg-red-500 hover:bg-red-600 text-white rounded text-sm"
                                onClick={() => setOpen(false)}
                            >
                                Close Dialog
                            </button>
                        </div>
                    </Dialog.Content>
                </Dialog.Portal>
            </Dialog.Root>
        </div>
    );
}
