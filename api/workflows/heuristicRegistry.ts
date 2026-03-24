import type { HeuristicFn } from './workflowTypes';

const heuristicRegistry = new Map<string, HeuristicFn>();

export function getHeuristic(name: string): HeuristicFn | undefined {
    return heuristicRegistry.get(name);
}

export function registerHeuristic(name: string, fn: HeuristicFn): void {
    heuristicRegistry.set(name, fn);
}
