import { registerHeuristic } from '../heuristicRegistry';

/**
 * Register all heuristics.
 *
 * Heuristics act as a labeled registry: each name maps to an internal function
 * that auto-populates a workflow context field. The engine calls these by name
 * when a context field has a `heuristic` property in its definition.
 */
export function registerHeuristics(): void {
    // Suggest the best cost function for skull stripping.
    // ls (Pearson) is fast and works well for same-modality T1→MNI registration.
    registerHeuristic('suggest-cost-function', async () => {
        return 'ls';
    });

    // Suggest the best MNI template resolution.
    // 2mm is a good balance of speed vs accuracy for most T1w images.
    registerHeuristic('suggest-template', async () => {
        return '2mm';
    });
}
