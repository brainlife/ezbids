import { useState, forwardRef, useImperativeHandle, useCallback } from 'react';
import toast from 'react-hot-toast';

import { useAppSelector, useAppDispatch } from '../../store/hooks';
import { setReadme, type DatasetDescription } from '../../store/slices/ezbidsSlice';

// ── Types ─────────────────────────────────────────────────────────────

export interface DescriptionHandle {
    isValid: (cb: (err: string | null) => void) => void;
}

// ── Tag Input Component ───────────────────────────────────────────────
// Replaces el-select with multiple/filterable/allow-create behavior

interface TagInputProps {
    value: string[] | undefined | null;
    onChange: (val: string[]) => void;
    placeholder: string;
}

function TagInput({ value, onChange, placeholder }: TagInputProps) {
    const [inputVal, setInputVal] = useState('');

    function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
        if (e.key === 'Enter' && inputVal.trim()) {
            e.preventDefault();
            if (!value.includes(inputVal.trim())) {
                onChange([...(value || []), inputVal.trim()]);
            }
            setInputVal('');
        }
    }

    function removeTag(idx: number) {
        onChange((value || []).filter((_, i) => i !== idx));
    }

    const tags = value || [];

    return (
        <div className="border rounded px-2 py-1 flex flex-wrap gap-1 items-center min-h-[38px] w-full bg-white">
            {tags.map((tag, idx) => (
                <span
                    key={idx}
                    className="bg-blue-100 text-blue-800 text-sm px-2 py-0.5 rounded flex items-center gap-1"
                >
                    {tag}
                    <button
                        type="button"
                        className="text-blue-500 hover:text-blue-700 font-bold leading-none"
                        onClick={() => removeTag(idx)}
                    >
                        x
                    </button>
                </span>
            ))}
            <input
                className="flex-1 min-w-[150px] outline-none text-sm py-1"
                value={inputVal}
                onChange={(e) => setInputVal(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={tags.length === 0 ? placeholder : ''}
            />
        </div>
    );
}

// ── Component ─────────────────────────────────────────────────────────

const Description = forwardRef<DescriptionHandle>(function Description(_props, ref) {
    const dispatch = useAppDispatch();
    const ezbids = useAppSelector((s) => s.ezbids.data);

    const dd = ezbids.datasetDescription;
    const readme = ezbids.readme;

    // Validation errors
    const [errors, setErrors] = useState<Record<string, string>>({});

    // Expose isValid to parent
    useImperativeHandle(ref, () => ({
        isValid(cb: (err: string | null) => void) {
            const newErrors: Record<string, string> = {};
            if (!dd.Name || dd.Name.trim() === '') {
                newErrors.Name = 'Please enter dataset description';
            }
            if (!dd.BIDSVersion || dd.BIDSVersion.trim() === '') {
                newErrors.BIDSVersion = 'Please enter BIDS Version';
            }
            setErrors(newErrors);
            if (Object.keys(newErrors).length > 0) {
                cb('Please correct all issues on the form.');
            } else {
                cb(null);
            }
        },
    }));

    // Since dd is from Redux (immutable), we dispatch updates through the store.
    // We use a helper that updates the ezbids data via updateEzbids or direct mutations.
    // For simplicity, we dispatch a full ezbids update on each field change.
    // However, the ezbidsSlice uses Immer so we can use updateEzbids with partial data.
    // Actually, the dd object is part of state.ezbids.data.datasetDescription.
    // We need a way to update individual fields. Let's use a local updater pattern
    // that dispatches updateEzbids with the changed datasetDescription.

    const updateDD = useCallback(
        (field: keyof DatasetDescription, value: any) => {
            // We dispatch a full ezbids update. The processEzbidsData in the slice
            // does Object.assign, so we can pass partial data.
            // But that would overwrite other fields. Instead, we need to pass the full
            // datasetDescription with the updated field.
            // Since the slice uses Immer, we can use a specific action.
            // Looking at the slice, there's updateEzbids which does Object.assign(state.data, payload).
            // Let's pass { datasetDescription: { ...dd, [field]: value } }
            dispatch({
                type: 'ezbids/updateEzbids',
                payload: {
                    datasetDescription: { ...dd, [field]: value },
                },
            });
        },
        [dd, dispatch]
    );

    const updateGeneratedByField = useCallback(
        (field: string, value: string) => {
            const newGeneratedBy = [...dd.GeneratedBy];
            newGeneratedBy[0] = { ...newGeneratedBy[0], [field]: value };
            updateDD('GeneratedBy', newGeneratedBy);
        },
        [dd.GeneratedBy, updateDD]
    );

    const updateContainerField = useCallback(
        (field: string, value: string) => {
            const newGeneratedBy = [...dd.GeneratedBy];
            newGeneratedBy[0] = {
                ...newGeneratedBy[0],
                Container: { ...newGeneratedBy[0].Container, [field]: value },
            };
            updateDD('GeneratedBy', newGeneratedBy);
        },
        [dd.GeneratedBy, updateDD]
    );

    // ── Render ────────────────────────────────────────────────────────

    const formItemClass = 'flex items-start gap-4 mb-4';
    const labelClass = 'w-[150px] shrink-0 text-right text-sm font-medium text-gray-700 pt-2';
    const inputClass = 'border rounded px-3 py-2 w-full text-sm outline-none focus:ring-2 focus:ring-blue-300';
    const errorClass = 'text-red-500 text-xs mt-1';

    return (
        <div className="p-5">
            <p>
                Please enter as much information you like to include in the <b>dataset_description.json</b>. For
                specific information and examples, see{' '}
                <a
                    href="https://bids-specification.readthedocs.io/en/stable/03-modality-agnostic-files.html#dataset_descriptionjson"
                    target="_blank"
                    rel="noreferrer"
                    className="text-blue-600 underline"
                >
                    here
                </a>{' '}
                and{' '}
                <a
                    href="https://github.com/bids-standard/bids-examples/blob/master/ds000117/dataset_description.json"
                    target="_blank"
                    rel="noreferrer"
                    className="text-blue-600 underline"
                >
                    here
                </a>
            </p>
            <br />

            <form>
                {/* Dataset Name */}
                <div className={formItemClass}>
                    <label className={labelClass}>Dataset Name</label>
                    <div className="flex-1">
                        <input
                            className={`${inputClass} ${errors.Name ? 'border-red-500' : ''}`}
                            value={dd.Name}
                            onChange={(e) => updateDD('Name', e.target.value)}
                        />
                        {errors.Name && <div className={errorClass}>{errors.Name}</div>}
                    </div>
                </div>

                {/* BIDSVersion */}
                <div className={formItemClass}>
                    <label className={labelClass}>BIDSVersion</label>
                    <div className="flex-1">
                        <input className={`${inputClass} bg-gray-100`} value={dd.BIDSVersion} disabled />
                        {errors.BIDSVersion && <div className={errorClass}>{errors.BIDSVersion}</div>}
                    </div>
                </div>

                {/* HEDVersion */}
                <div className={formItemClass}>
                    <label className={labelClass}>HEDVersion</label>
                    <div className="flex-1">
                        <TagInput
                            value={dd.HEDVersion}
                            onChange={(val) => updateDD('HEDVersion', val)}
                            placeholder="Enter HED tags"
                        />
                    </div>
                </div>

                {/* DatasetType */}
                <div className={formItemClass}>
                    <label className={labelClass}>DatasetType</label>
                    <div className="flex-1">
                        <input className={`${inputClass} bg-gray-100`} value={dd.DatasetType} disabled />
                    </div>
                </div>

                {/* License */}
                <div className={formItemClass}>
                    <label className={labelClass}>License</label>
                    <div className="flex-1">
                        <input
                            className={inputClass}
                            value={dd.License}
                            onChange={(e) => updateDD('License', e.target.value)}
                        />
                    </div>
                </div>

                {/* Authors */}
                <div className={formItemClass}>
                    <label className={labelClass}>Authors</label>
                    <div className="flex-1">
                        <TagInput
                            value={dd.Authors}
                            onChange={(val) => updateDD('Authors', val)}
                            placeholder="Enter Author Names"
                        />
                    </div>
                </div>

                {/* Acknowledgements */}
                <div className={formItemClass}>
                    <label className={labelClass}>Acknowledgements</label>
                    <div className="flex-1">
                        <textarea
                            className={inputClass}
                            rows={2}
                            placeholder="Any acknowledgements you'd like to add.."
                            value={dd.Acknowledgements}
                            onChange={(e) => updateDD('Acknowledgements', e.target.value)}
                        />
                    </div>
                </div>

                {/* How To Acknowledge */}
                <div className={formItemClass}>
                    <label className={labelClass}>How To Acknowledge</label>
                    <div className="flex-1">
                        <textarea
                            className={inputClass}
                            rows={2}
                            placeholder="Enter how you want your users to acknowledge when they use this dataset"
                            value={dd.HowToAcknowledge}
                            onChange={(e) => updateDD('HowToAcknowledge', e.target.value)}
                        />
                    </div>
                </div>

                {/* Funding Sources */}
                <div className={formItemClass}>
                    <label className={labelClass}>Funding Sources</label>
                    <div className="flex-1">
                        <TagInput
                            value={dd.Funding}
                            onChange={(val) => updateDD('Funding', val)}
                            placeholder="Funding sources"
                        />
                    </div>
                </div>

                {/* EthicsApprovals */}
                <div className={formItemClass}>
                    <label className={labelClass}>EthicsApprovals</label>
                    <div className="flex-1">
                        <TagInput
                            value={dd.EthicsApprovals}
                            onChange={(val) => updateDD('EthicsApprovals', val)}
                            placeholder="Enter list of ethics committee approvals of the research"
                        />
                    </div>
                </div>

                {/* References and Links */}
                <div className={formItemClass}>
                    <label className={labelClass}>References and Links</label>
                    <div className="flex-1">
                        <TagInput
                            value={dd.ReferencesAndLinks}
                            onChange={(val) => updateDD('ReferencesAndLinks', val)}
                            placeholder="Add any references / citations / links"
                        />
                    </div>
                </div>

                {/* Dataset DOI */}
                <div className={formItemClass}>
                    <label className={labelClass}>Dataset DOI</label>
                    <div className="flex-1">
                        <input
                            className={inputClass}
                            placeholder="DOI assigned for this dataset"
                            value={dd.DatasetDOI}
                            onChange={(e) => updateDD('DatasetDOI', e.target.value)}
                        />
                    </div>
                </div>

                {/* GeneratedBy */}
                <div className={formItemClass}>
                    <label className={labelClass}>GeneratedBy</label>
                    <div className="flex-1">
                        {dd.GeneratedBy && dd.GeneratedBy[0] && (
                            <div className="space-y-3">
                                {Object.entries(dd.GeneratedBy[0]).map(([key, value]) => {
                                    if (key === 'Container') {
                                        return (
                                            <div key={key}>
                                                <div className={formItemClass}>
                                                    <label className="w-[120px] shrink-0 text-right text-sm font-medium text-gray-600 pt-2">
                                                        {key}
                                                    </label>
                                                    <div className="flex-1" />
                                                </div>
                                                {dd.GeneratedBy[0].Container &&
                                                    Object.entries(dd.GeneratedBy[0].Container).map(
                                                        ([cKey, cValue]) => (
                                                            <div key={cKey} className={formItemClass}>
                                                                <label className="w-[120px] shrink-0 text-right text-sm font-medium text-gray-500 pt-2">
                                                                    {cKey}
                                                                </label>
                                                                <div className="flex-1">
                                                                    <input
                                                                        className={inputClass}
                                                                        placeholder={String(cValue)}
                                                                        value={String(cValue)}
                                                                        onChange={(e) =>
                                                                            updateContainerField(cKey, e.target.value)
                                                                        }
                                                                    />
                                                                </div>
                                                            </div>
                                                        )
                                                    )}
                                            </div>
                                        );
                                    }
                                    return (
                                        <div key={key} className={formItemClass}>
                                            <label className="w-[120px] shrink-0 text-right text-sm font-medium text-gray-600 pt-2">
                                                {key}
                                            </label>
                                            <div className="flex-1">
                                                <input
                                                    className={inputClass}
                                                    placeholder={String(value)}
                                                    value={String(value)}
                                                    onChange={(e) => updateGeneratedByField(key, e.target.value)}
                                                />
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        )}
                    </div>
                </div>

                {/* Separator */}
                <div className="border-t border-black/10 my-4" />

                {/* README */}
                <div className={formItemClass}>
                    <label className={labelClass}>README(.md)</label>
                    <div className="flex-1">
                        <textarea
                            className={inputClass}
                            rows={10}
                            placeholder="BIDS README. Should not be empty"
                            value={readme}
                            onChange={(e) => dispatch(setReadme(e.target.value))}
                        />
                    </div>
                </div>
            </form>
        </div>
    );
});

export default Description;
