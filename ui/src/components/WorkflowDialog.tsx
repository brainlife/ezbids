import { useState, useCallback } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { Cross2Icon } from '@radix-ui/react-icons';
import axios from '../axios.instance';
import { useAppSelector } from '../store/hooks';

interface WorkflowListItem {
    name: string;
    description: string;
    menu: string;
}

interface ContextFieldDef {
    type: string;
    description: string;
    heuristic?: string;
    default?: unknown;
    enum?: unknown[];
    min?: number;
    max?: number;
}

interface FormSectionDef {
    title: string;
    description?: string;
    fields: string[];
    component?: string;
    buttonText?: string;
}

interface WorkflowDefinition {
    name: string;
    version: string;
    description: string;
    menu: string;
    inputs: Record<string, { type: string; description: string }>;
    context?: { description?: string; fields: Record<string, ContextFieldDef> };
    form?: { sections: FormSectionDef[] };
    steps: Record<string, unknown>;
    outputs: Record<string, { type: string; ref: string }>;
}

interface WorkflowRunState {
    workflowName: string;
    inputs: Record<string, unknown>;
    context: Record<string, unknown>;
    stepOutputs: Record<string, Record<string, unknown>>;
    status: string;
    error?: string;
}

export default function WorkflowDialog() {
    const config = useAppSelector((s) => s.session.config);
    const ezbids = useAppSelector((s) => s.ezbids);
    // Handle both web (/api/ezbids → /workflow) and Electron (http://host:port → /workflow)
    const apiBase = config.apihost.replace(/\/api\/ezbids\/?$/, '') + '/workflow';

    const [listOpen, setListOpen] = useState(false);
    const [runOpen, setRunOpen] = useState(false);
    const [workflows, setWorkflows] = useState<WorkflowListItem[]>([]);
    const [definition, setDefinition] = useState<WorkflowDefinition | null>(null);
    const [runId, setRunId] = useState<string | null>(null);
    const [runState, setRunState] = useState<WorkflowRunState | null>(null);
    const [currentSection, setCurrentSection] = useState(0);
    const [loading, setLoading] = useState(false);
    const [loadingMsg, setLoadingMsg] = useState('');
    const [executing, setExecuting] = useState(false);

    const totalSections = definition?.form?.sections?.length || 0;
    const activeSection = definition?.form?.sections?.[currentSection] || null;

    const openList = useCallback(async () => {
        setListOpen(true);
        try {
            const res = await axios.get(apiBase);
            setWorkflows(res.data);
        } catch {
            setWorkflows([]);
        }
    }, [apiBase]);

    const selectWorkflow = useCallback(
        async (name: string) => {
            setListOpen(false);
            setRunOpen(true);
            setLoading(true);
            setLoadingMsg('Starting workflow...');
            setCurrentSection(0);
            setRunState(null);
            setDefinition(null);

            try {
                // Build workflow inputs from current session data
                const workflowInputs: Record<string, unknown> = {};
                // Auto-detect anatomical volumes for workflows that need them
                if (ezbids?.objects) {
                    const volumes = ezbids.objects
                        .filter((o: any) => o._type?.startsWith('anat') && !o.exclude && !o._exclude)
                        .flatMap((o: any) =>
                            o.items.filter((i: any) => i.path?.endsWith('.nii.gz')).map((i: any) => i.path)
                        )
                        .filter(Boolean);
                    if (volumes.length > 0) {
                        workflowInputs.volumes = volumes;
                    }
                }
                const startRes = await axios.post(`${apiBase}/start`, {
                    name,
                    inputs: workflowInputs,
                });
                setRunId(startRes.data.runId);
                setRunState(startRes.data.runState);
                setDefinition(startRes.data.definition);

                if (startRes.data.autoSteps?.length > 0) {
                    setLoadingMsg('Running auto steps...');
                    const autoRes = await axios.post(`${apiBase}/${startRes.data.runId}/auto-steps`);
                    setRunState(autoRes.data.runState);
                }

                const def = startRes.data.definition as WorkflowDefinition;
                if (def?.context?.fields) {
                    for (const [fieldName, field] of Object.entries(def.context.fields)) {
                        if (field.heuristic) {
                            setLoadingMsg(`Computing ${fieldName}...`);
                            try {
                                const hRes = await axios.post(`${apiBase}/${startRes.data.runId}/heuristic`, {
                                    fieldName,
                                });
                                setRunState((prev) => (prev ? { ...prev, context: hRes.data.context } : prev));
                            } catch (err) {
                                console.warn(`Heuristic failed for ${fieldName}:`, err);
                            }
                        }
                    }
                }
            } catch (err) {
                console.error('Failed to start workflow:', err);
                setRunState((prev) => (prev ? { ...prev, status: 'error', error: 'Failed to start workflow' } : prev));
            } finally {
                setLoading(false);
            }
        },
        [apiBase]
    );

    const getFieldDef = (name: string): ContextFieldDef | null => definition?.context?.fields?.[name] || null;

    const contextValue = (name: string): unknown => runState?.context?.[name];

    const setContextValue = async (fieldName: string, value: unknown) => {
        if (!runId || !runState) return;
        setRunState({ ...runState, context: { ...runState.context, [fieldName]: value } });
        try {
            await axios.patch(`${apiBase}/${runId}/context`, { fieldName, value });
        } catch (err) {
            console.error('Failed to update context:', err);
        }
    };

    const executeAll = async () => {
        if (!runId) return;
        setExecuting(true);
        try {
            const res = await axios.post(`${apiBase}/${runId}/execute-all`);
            setRunState(res.data.runState);
        } catch {
            setRunState((prev) => (prev ? { ...prev, status: 'error', error: 'Execution failed' } : prev));
        } finally {
            setExecuting(false);
        }
    };

    const handleClose = async () => {
        if (runId) {
            try {
                await axios.post(`${apiBase}/${runId}/cancel`);
            } catch {
                /* ignore */
            }
        }
        setRunOpen(false);
        setRunId(null);
        setRunState(null);
        setDefinition(null);
        setCurrentSection(0);
    };

    // Group workflows by menu
    const grouped = workflows.reduce<Record<string, WorkflowListItem[]>>((acc, wf) => {
        if (!acc[wf.menu]) acc[wf.menu] = [];
        acc[wf.menu].push(wf);
        return acc;
    }, {});

    const renderField = (fieldName: string) => {
        const def = getFieldDef(fieldName);
        if (!def) return null;
        const val = contextValue(fieldName);

        if (def.enum) {
            return (
                <select
                    className="w-full border border-gray-300 rounded px-3 py-2 text-sm"
                    value={String(val ?? '')}
                    onChange={(e) => setContextValue(fieldName, e.target.value)}
                >
                    {def.enum.map((opt) => (
                        <option key={String(opt)} value={String(opt)}>
                            {String(opt)}
                        </option>
                    ))}
                </select>
            );
        }
        if (def.type === 'boolean') {
            return (
                <button
                    className={`relative w-10 h-5 rounded-full transition-colors ${
                        val ? 'bg-blue-600' : 'bg-gray-300'
                    }`}
                    onClick={() => setContextValue(fieldName, !val)}
                >
                    <span
                        className={`absolute top-0.5 w-4 h-4 bg-white rounded-full transition-transform ${
                            val ? 'translate-x-5' : 'translate-x-0.5'
                        }`}
                    />
                </button>
            );
        }
        if (def.type === 'number') {
            return (
                <input
                    type="number"
                    className="w-full border border-gray-300 rounded px-3 py-2 text-sm"
                    value={val != null ? Number(val) : ''}
                    min={def.min}
                    max={def.max}
                    onChange={(e) => setContextValue(fieldName, e.target.value ? Number(e.target.value) : undefined)}
                />
            );
        }
        return (
            <input
                type="text"
                className="w-full border border-gray-300 rounded px-3 py-2 text-sm"
                value={String(val ?? '')}
                onChange={(e) => setContextValue(fieldName, e.target.value)}
            />
        );
    };

    return (
        <>
            <button
                className="w-full py-1.5 px-3 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded"
                onClick={openList}
            >
                Workflows
            </button>

            {/* Workflow list */}
            <Dialog.Root open={listOpen} onOpenChange={setListOpen}>
                <Dialog.Portal>
                    <Dialog.Overlay className="fixed inset-0 bg-black/40" />
                    <Dialog.Content className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-white rounded-lg shadow-xl w-[500px] max-h-[85vh] overflow-auto p-6">
                        <Dialog.Title className="text-lg font-semibold mb-4">Available Workflows</Dialog.Title>
                        <Dialog.Close className="absolute top-4 right-4">
                            <Cross2Icon />
                        </Dialog.Close>
                        {workflows.length === 0 ? (
                            <p className="text-center text-gray-400 py-5">No workflows available.</p>
                        ) : (
                            Object.entries(grouped).map(([menu, items]) => (
                                <div key={menu} className="mb-4">
                                    <div className="font-semibold text-gray-700 mb-2">{menu}</div>
                                    {items.map((wf) => (
                                        <div
                                            key={wf.name}
                                            className="px-3 py-2 rounded cursor-pointer hover:bg-gray-100 mb-1"
                                            onClick={() => selectWorkflow(wf.name)}
                                        >
                                            <div className="font-medium">{wf.name}</div>
                                            <div className="text-xs text-gray-500">{wf.description}</div>
                                        </div>
                                    ))}
                                </div>
                            ))
                        )}
                    </Dialog.Content>
                </Dialog.Portal>
            </Dialog.Root>

            {/* Workflow run */}
            <Dialog.Root
                open={runOpen}
                onOpenChange={(open) => {
                    if (!open) handleClose();
                }}
            >
                <Dialog.Portal>
                    <Dialog.Overlay className="fixed inset-0 bg-black/40" />
                    <Dialog.Content className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-white rounded-lg shadow-xl w-[700px] max-h-[85vh] overflow-auto p-6">
                        <Dialog.Title className="text-lg font-semibold mb-4">
                            {definition?.description || 'Workflow'}
                        </Dialog.Title>
                        <Dialog.Close className="absolute top-4 right-4">
                            <Cross2Icon />
                        </Dialog.Close>

                        {loading && (
                            <div className="text-center py-10">
                                <div className="text-2xl animate-spin mb-3">⟳</div>
                                <div className="text-gray-500">{loadingMsg}</div>
                            </div>
                        )}

                        {runState?.status === 'error' && (
                            <div className="bg-red-50 border border-red-200 rounded p-3 mb-4 text-red-700 text-sm">
                                {runState.error || 'An error occurred'}
                            </div>
                        )}

                        {!loading && definition?.form && (
                            <>
                                {/* Stepper */}
                                <div className="flex items-center gap-1 mb-6">
                                    {definition.form.sections.map((sec, i) => (
                                        <div key={i} className="flex items-center gap-1">
                                            <div
                                                className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-medium ${
                                                    i < currentSection
                                                        ? 'bg-green-500 text-white'
                                                        : i === currentSection
                                                        ? 'bg-blue-600 text-white'
                                                        : 'bg-gray-200 text-gray-500'
                                                }`}
                                            >
                                                {i + 1}
                                            </div>
                                            <span className="text-xs text-gray-500 hidden sm:inline">{sec.title}</span>
                                            {i < totalSections - 1 && <div className="w-4 h-px bg-gray-300" />}
                                        </div>
                                    ))}
                                </div>

                                {activeSection && (
                                    <div className="min-h-[200px]">
                                        {activeSection.description && (
                                            <p className="text-sm text-gray-500 mb-4">{activeSection.description}</p>
                                        )}
                                        {activeSection.component ? (
                                            <div className="bg-gray-50 p-5 rounded text-center text-gray-500">
                                                Custom component: <code>{activeSection.component}</code>
                                            </div>
                                        ) : (
                                            <div className="space-y-4">
                                                {activeSection.fields.map((fieldName) => (
                                                    <div key={fieldName}>
                                                        <label className="block text-sm font-medium text-gray-700 mb-1">
                                                            {getFieldDef(fieldName)?.description || fieldName}
                                                        </label>
                                                        {renderField(fieldName)}
                                                    </div>
                                                ))}
                                            </div>
                                        )}
                                    </div>
                                )}

                                <div className="flex justify-between mt-6 pt-4 border-t border-gray-200">
                                    {currentSection > 0 ? (
                                        <button
                                            className="px-4 py-2 border border-gray-300 rounded hover:bg-gray-50"
                                            onClick={() => setCurrentSection(currentSection - 1)}
                                        >
                                            Back
                                        </button>
                                    ) : (
                                        <div />
                                    )}
                                    <div className="flex gap-2">
                                        <button
                                            className="px-4 py-2 border border-gray-300 rounded hover:bg-gray-50"
                                            onClick={handleClose}
                                        >
                                            Cancel
                                        </button>
                                        {currentSection < totalSections - 1 ? (
                                            <button
                                                className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
                                                onClick={() => setCurrentSection(currentSection + 1)}
                                            >
                                                Next
                                            </button>
                                        ) : (
                                            <button
                                                className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
                                                disabled={executing}
                                                onClick={executeAll}
                                            >
                                                {executing ? 'Running...' : activeSection?.buttonText || 'Run'}
                                            </button>
                                        )}
                                    </div>
                                </div>
                            </>
                        )}

                        {!loading && definition && !definition.form && (
                            <div className="text-center py-5">
                                <button
                                    className="px-6 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
                                    disabled={executing}
                                    onClick={executeAll}
                                >
                                    {executing ? 'Running...' : 'Run'}
                                </button>
                            </div>
                        )}

                        {runState?.status === 'completed' && (
                            <div className="text-center mt-4 p-6 bg-green-50 rounded">
                                <div className="text-green-600 text-xl mb-2">✓</div>
                                <div className="font-medium text-green-700">Workflow completed</div>
                                <button
                                    className="mt-3 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
                                    onClick={handleClose}
                                >
                                    Close
                                </button>
                            </div>
                        )}
                    </Dialog.Content>
                </Dialog.Portal>
            </Dialog.Root>
        </>
    );
}
