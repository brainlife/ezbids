import express = require('express')
import { getWorkflowDefinitions } from './workflows/workflowLoader'
import {
  startWorkflow,
  getRunState,
  getDefinitionForRun,
  getAutoRunnableSteps,
  runHeuristic,
  updateContext,
  executeStep,
  executeAllSteps,
  runAutoSteps,
  cancelRun
} from './workflows/workflowEngine'
import type { WorkflowListItem } from './workflows/workflowTypes'

const router = express.Router()

// GET /workflow — list available workflows
router.get('/', (_req, res) => {
  const workflows = getWorkflowDefinitions()
  const items: WorkflowListItem[] = []
  for (const wf of workflows.values()) {
    items.push({
      name: wf.name,
      description: wf.description,
      menu: wf.menu
    })
  }
  res.json(items)
})

// GET /workflow/:name — get a workflow definition
router.get('/:name', (req, res) => {
  const wf = getWorkflowDefinitions().get(req.params.name)
  if (!wf) {
    return res.status(404).json({ error: `Unknown workflow: ${req.params.name}` })
  }
  res.json(wf)
})

// POST /workflow/start — start a workflow run
router.post('/start', (req, res) => {
  try {
    const { name, inputs } = req.body as { name: string; inputs: Record<string, unknown> }
    const { runId, runState, definition } = startWorkflow(name, inputs)
    const autoSteps = getAutoRunnableSteps(definition)
    res.json({ runId, runState, definition, autoSteps })
  } catch (err) {
    res.status(400).json({ error: err instanceof Error ? err.message : String(err) })
  }
})

// POST /workflow/:runId/auto-steps — run auto-runnable steps
router.post('/:runId/auto-steps', async (req, res, next) => {
  try {
    const executed = await runAutoSteps(req.params.runId)
    const state = getRunState(req.params.runId)
    res.json({ executed, runState: state })
  } catch (err) {
    next(err)
  }
})

// POST /workflow/:runId/heuristic — run a heuristic for a context field
router.post('/:runId/heuristic', async (req, res, next) => {
  try {
    const { fieldName } = req.body as { fieldName: string }
    const value = await runHeuristic(req.params.runId, fieldName)
    const state = getRunState(req.params.runId)
    res.json({ value, context: state?.context })
  } catch (err) {
    next(err)
  }
})

// PATCH /workflow/:runId/context — update a context field
router.patch('/:runId/context', (req, res) => {
  try {
    const { fieldName, value } = req.body as { fieldName: string; value: unknown }
    updateContext(req.params.runId, fieldName, value)
    const state = getRunState(req.params.runId)
    res.json({ context: state?.context })
  } catch (err) {
    res.status(400).json({ error: err instanceof Error ? err.message : String(err) })
  }
})

// POST /workflow/:runId/step/:stepName — execute a single step
router.post('/:runId/step/:stepName', async (req, res, next) => {
  try {
    const outputs = await executeStep(req.params.runId, req.params.stepName)
    const state = getRunState(req.params.runId)
    res.json({ outputs, runState: state })
  } catch (err) {
    next(err)
  }
})

// POST /workflow/:runId/execute-all — execute all remaining steps
router.post('/:runId/execute-all', async (req, res, next) => {
  try {
    const outputs = await executeAllSteps(req.params.runId)
    const state = getRunState(req.params.runId)
    res.json({ outputs, runState: state })
  } catch (err) {
    next(err)
  }
})

// POST /workflow/:runId/cancel — cancel a run
router.post('/:runId/cancel', (req, res) => {
  cancelRun(req.params.runId)
  res.json({ success: true })
})

// GET /workflow/:runId/state — get current run state
router.get('/:runId/state', (req, res) => {
  const state = getRunState(req.params.runId)
  const definition = getDefinitionForRun(req.params.runId)
  if (!state) {
    return res.status(404).json({ error: `No active run: ${req.params.runId}` })
  }
  res.json({ runState: state, definition })
})

module.exports = router
