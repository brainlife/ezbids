import type { ToolExecutor } from './workflowTypes';

const toolExecutors = new Map<string, ToolExecutor>();

export function getToolExecutor(name: string): ToolExecutor | undefined {
    return toolExecutors.get(name);
}

export function registerToolExecutor(name: string, executor: ToolExecutor): void {
    toolExecutors.set(name, executor);
}
