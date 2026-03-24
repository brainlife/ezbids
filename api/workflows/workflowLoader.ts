import fs = require('fs');
import path = require('path');
import type { ToolDefinition, WorkflowDefinition } from './workflowTypes';

const toolDefinitions = new Map<string, ToolDefinition>();
const workflowDefinitions = new Map<string, WorkflowDefinition>();

function getWorkflowsRoot(): string {
    return path.resolve(__dirname, '..', '..', 'workflows');
}

function loadJsonFiles<T>(dir: string): T[] {
    if (!fs.existsSync(dir)) return [];
    return fs
        .readdirSync(dir)
        .filter((f) => f.endsWith('.json'))
        .map((f) => JSON.parse(fs.readFileSync(path.join(dir, f), 'utf-8')) as T);
}

export function loadAllDefinitions(): void {
    const root = getWorkflowsRoot();

    const tools = loadJsonFiles<ToolDefinition>(path.join(root, 'tools'));
    for (const tool of tools) {
        toolDefinitions.set(tool.name, tool);
    }

    const workflows = loadJsonFiles<WorkflowDefinition>(path.join(root, 'workflows'));
    for (const wf of workflows) {
        workflowDefinitions.set(wf.name, wf);
    }

    // eslint-disable-next-line no-console
    console.log(`[workflow] Loaded ${toolDefinitions.size} tools, ${workflowDefinitions.size} workflows`);
}

export function getToolDefinitions(): Map<string, ToolDefinition> {
    return toolDefinitions;
}

export function getWorkflowDefinitions(): Map<string, WorkflowDefinition> {
    return workflowDefinitions;
}
