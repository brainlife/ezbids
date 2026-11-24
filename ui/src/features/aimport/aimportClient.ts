// Client of the local aimport engine (desktop app only). Calls go through the Electron main process,
// which holds the engine's token; nothing here talks to the network directly.

export type Stage = 'idle' | 'scanning' | 'planned' | 'executing' | 'validated' | 'invalid' | 'failed';

export interface Issue {
    code: string;
    severity: string;
    message: string;
    files: string[];
}

export interface Status {
    stage: Stage;
    message?: string;
    warnings?: string[];
    output_dir?: string;
    validation?: {
        ok: boolean;
        error_count: number;
        warning_count: number;
        errors: Issue[];
        warnings: Issue[];
        validator_version?: string;
        bids_version?: string;
    };
    manifest?: Record<string, string[]>;
}

export interface PlanEntry {
    id: string;
    subject: string;
    session: string | null;
    datatype: string | null;
    suffix: string | null;
    entities: Record<string, string>;
    deface: boolean;
    exclude: boolean;
    status: 'ok' | 'unknown' | 'unsupported' | 'excluded_by_default';
    source: string;
    confidence: number;
    reason: string;
    description: string;
    agent_note: string;
}

export interface Plan {
    entries: PlanEntry[];
    approved: boolean;
    deface_method: string;
    dataset_name: string;
    readme: string;
    warnings: string[];
    ancillary: { id: string; action: string; reason: string; flags: string[] }[];
}

export interface Box {
    x: number;
    y: number;
    width: number;
    height: number;
}

interface AimportBridge {
    pickFolder(): Promise<string | null>;
    start(inputDir: string): Promise<{ ok: boolean; inputDir?: string; error?: string }>;
    api(method: 'GET' | 'POST' | 'PATCH', path: string, body?: unknown): Promise<{ status: number; data: any }>;
    openViewer(bounds: Box): Promise<{ ok: boolean; error?: string }>;
    setViewerBounds(bounds: Box): Promise<void>;
    closeViewer(): Promise<void>;
    showOutput(): Promise<{ ok: boolean }>;
    stop(): Promise<void>;
}

declare global {
    interface Window {
        aimport?: AimportBridge;
    }
}

export const hasAimport = (): boolean => !!window.aimport;

const bridge = (): AimportBridge => {
    if (!window.aimport) throw new Error('AI import is only available in the desktop app');
    return window.aimport;
};

export class EngineError extends Error {
    constructor(public status: number, detail: unknown) {
        super(typeof detail === 'string' ? detail : JSON.stringify(detail));
    }
}

async function call<T>(method: 'GET' | 'POST' | 'PATCH', path: string, body?: unknown): Promise<T> {
    const res = await bridge().api(method, path, body);
    if (res.status >= 400) throw new EngineError(res.status, res.data?.detail ?? res.data);
    return res.data as T;
}

export const engine = {
    pickFolder: () => bridge().pickFolder(),
    start: (dir: string) => bridge().start(dir),
    status: () => call<Status>('GET', '/status'),
    scan: (projectId: string) =>
        call('POST', '/scan', { project_id: projectId, existing_subjects: [], target: 'bids' }),
    plan: () => call<Plan>('GET', '/plan'),
    edit: (body: Record<string, unknown>) => call<Plan>('PATCH', '/plan', body),
    approve: (defaceMethod: string) => call<Plan>('POST', '/approve', { deface_method: defaceMethod }),
    execute: () => call('POST', '/execute'),
    openViewer: (box: Box) => bridge().openViewer(box),
    setViewerBounds: (box: Box) => bridge().setViewerBounds(box),
    closeViewer: () => bridge().closeViewer(),
    showOutput: () => bridge().showOutput(),
};
