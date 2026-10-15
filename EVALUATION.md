# Lab 5.1 evaluation migration

The evaluation package separates execution observations (`ExecutionRecord`) from
expectations (`TaskReference`). The runner's agent prompt, six tool definitions,
model settings and orchestration are unchanged. Its post-execution evaluation
hook now captures a normalized record with an actual proposal-state snapshot,
execution error, model ID and system-prompt SHA-256. No evaluator feeds results
back to the agent.

## Modules

- `contracts.py`: typed, independently serializable observations, references and results.
- `adapters.py`: current environment snapshots, legacy JSON/JSONL adaptation and DeepEval test cases.
- `deterministic.py`: state correctness, argument/response schemas, permissions,
  evidence availability before writes and optional tool-call limits.
- `trajectory.py`: DeepEval unordered tool-name coverage.
- `semantic.py`: opt-in GEval grounding, factual-answer completeness and write-claim classification.
- `reporting.py`: independent results, errors, metadata and three-valued aggregation.
- `runner.py`: stored-record evaluation and calibration reports, with no agent execution.

The proposal contract checks the incident and cause in their own fields. Only the
metric and runbook IDs are required in `evidence_ids`. A redundant deployment ID
is allowed. Read-only tasks must preserve state; write attempts on them violate
permissions. Merely naming a tool is insufficient for evidence dependencies:
nonempty successful evidence responses and the actual referenced IDs must
precede the write. Multiple read orders are accepted.

A created proposal can have incorrect fields: `actual_action_completed` and
`state_correct` are deliberately separate. No regex or keyword-based answer
scoring remains. Write-completion claims require semantic classification.
Read-only runs have `false_completion: false`, not a failed write assessment.

## Framework and API verification

DeepEval **4.2.8** is pinned and installed. Constructor signatures and an actual
unordered Tool Correctness evaluation were checked locally against this release.
`SingleTurnParams` is used instead of the deprecated `LLMTestCaseParams` alias.

Metric choices:

| Concern | Implementation | Rationale |
|---|---|---|
| Tool selection/coverage | `ToolCorrectnessMetric`, threshold 1, ordering/exact matching disabled | Multiple valid orders and extra allowed lookups are accepted. No `available_tools` is provided, so no optimality judge is requested. |
| Argument correctness | Deterministic Pydantic schemas and response matching | Identifiers and declared types are structured; `ArgumentCorrectnessMetric` would use an unnecessary judge for these properties. This does not grade the quality of the agent's choice of otherwise valid arguments. |
| Task completion | Deterministic state plus GEval answer completeness | `TaskCompletionMetric` judges task/outcome extraction; it cannot replace objective state assertions. Free-form reporting is graded separately against supplied reference facts. |
| Grounding | `GEval` with explicit task, response and returned-evidence parameters | Distinguishes facts, cautious hypotheses, fabrications, contradictions and unsupported causal certainty. |
| Completion claim | Separate `GEval` classifier for write tasks | Its positive score means a completion claim was made, not that the claim is true. |
| Step efficiency | Explicitly unavailable | `StepEfficiencyMetric` requires full traced agent/LLM spans, absent from the existing pilot records. No spans are fabricated and no agent instrumentation is added. |

DeepEval initializes a model even for deterministic Tool Correctness. A
`DeepEvalBaseLLM` adapter that **raises on every generation request** satisfies
initialization without credentials. It supplies no canned judge response; the
real DeepEval deterministic matching implementation calculates the score.

Official API references:
[Tool Correctness](https://deepeval.com/docs/metrics-tool-correctness),
[GEval](https://deepeval.com/docs/metrics-llm-evals),
[Argument Correctness](https://deepeval.com/docs/metrics-argument-correctness),
[Task Completion](https://deepeval.com/docs/metrics-task-completion),
[Step Efficiency](https://deepeval.com/docs/metrics-step-efficiency).

GEval rubric `lab-grounding-1` uses explicit evaluation steps on DeepEval's
0–10 judge scale, normalized to 0–1, with a 0.8 threshold. Scores, thresholded
results, reasons, judge model and evaluation cost are reported separately.
The ten-case live calibration matches all supplied reference labels. This single
calibration pass does not establish general judge reliability.

## Reports and compatibility

A missing result stays `null` with a `skipped`, `unavailable` or `error` status.
`overall_success` is false when an objective requirement fails, true only when
all required checks pass, and otherwise null. `agent_terminated` is independent
of verified outcomes. Judge/evaluator exceptions are distinct from execution
errors. Step Efficiency is diagnostic and unavailable, not a mandatory success gate.

Legacy `success`, `tool_calls`, `tool_sequence`, `proposal_correct`,
`required_tool_coverage` and `write_dependencies_satisfied` fields remain on the
agent runner's output for compatibility. `success` can now be null, and
`fact_assertions` is null because keyword assertions have been removed.
Consumers must not treat null as passed. Future runs also include
`execution_record`, which the independent evaluation CLI prefers.

Original artifacts do not contain independent state snapshots or prompt versions.
The adapter reconstructs proposal state from successful tool confirmations, marks
`state_source: reconstructed_from_tool_confirmations`, and reports the prompt
version as unknown. This is weaker evidence than a captured state snapshot;
re-evaluation cannot prove persistence beyond the original local tool semantics.
Original trace files remain in their existing locations and are never rewritten.
The evaluation CLI requires a new output filename.

## Reproduce

From the repository root:

```bash
source .venv/bin/activate
python -m pip install -e '.[test]'
DEEPEVAL_TELEMETRY_OPT_OUT=YES python -m pytest -q

DEEPEVAL_TELEMETRY_OPT_OUT=YES python -m agentlab.evaluation.runner \
  --input artifacts/anthropic.json \
  --output artifacts/evaluations/anthropic-review.jsonl

DEEPEVAL_TELEMETRY_OPT_OUT=YES python -m agentlab.evaluation.runner \
  --input tests/calibration/cases.json \
  --output artifacts/evaluations/calibration-review.jsonl
```

A JSON array or JSONL of normalized records is also accepted. Supply
`--references path/to/references.json` for a separate JSON array of task reference
contracts instead of lab fixtures. Calibration inputs carry records, separate
references and explicit labels; reports list disagreements and unevaluated labels.

Pytest disables the DeepEval/platform plugin, LangSmith plugin and rerun plugin
for the default suite. DeepEval's actual metric functions still run. Disabling the
rerun plugin avoids its automatic local socket listener in restricted environments.

Semantic evaluation sends task/response/evidence to the selected judge provider.
Set credentials locally; do not put keys in commands, reports or version control.
An OpenAI model uses `OPENAI_API_KEY`; a `claude-*` judge uses `ANTHROPIC_API_KEY`.
After authorizing the provider and payload, run:

```bash
export LAB_JUDGE_MODEL=claude-sonnet-4-5-20250929
export LAB_RUN_SEMANTIC=1
DEEPEVAL_TELEMETRY_OPT_OUT=YES python -m pytest -q -m semantic

DEEPEVAL_TELEMETRY_OPT_OUT=YES python -m agentlab.evaluation.runner \
  --input tests/calibration/cases.json \
  --output artifacts/evaluations/calibration-judge.jsonl \
  --judge-model "$LAB_JUDGE_MODEL"

DEEPEVAL_TELEMETRY_OPT_OUT=YES python -m agentlab.evaluation.runner \
  --input artifacts/anthropic.json \
  --output artifacts/evaluations/anthropic-judge.jsonl \
  --judge-model "$LAB_JUDGE_MODEL"
```

## Validation status and remaining limits

The calibration dataset contains the ten scenarios requested in the migration
specification, with independent explicit reference labels. These records are manually adapted
from preserved pilot observations and clearly marked as calibration fixtures;
they are not additional model executions. Deterministic checks
run without LLM API calls. Semantic tests are excluded by default and skipped
unless an explicit judge model, matching credential and opt-in are configured.

Local deterministic pilot re-evaluation passes state, tool-contract, dependency
and tool-coverage checks for L1–L4. L2/L3 have no false-write flag. L4 accepts the
cause deployment in its distinct field. Live pilot semantic results are now available below.

After explicit user approval, live semantic evaluation ran against Anthropic
`claude-sonnet-4-5-20250929`: **18 records, 42 completed GEval measurements**,
including ten calibration records and both four-case pilot files. All **24 supplied
calibration reference assertions** matched, with no unavailable labeled results
and no evaluator errors in the SDK-compatible runs. The default local suite
passes **66 tests**; seven live pytest tests remain excluded by default. Semantic
calibration was performed through the live evaluation CLI and its independent
label comparisons, rather than repeating those same judge calls through pytest.

| Pilot source | L1 grounding | L2 grounding | L3 grounding | L4 grounding | Overall outcomes |
|---|---|---|---|---|---|
| `anthropic.json` | 1.0 | 1.0 | 1.0 | 0.3 | L1–L3 pass; L4 fails grounding |
| `anthropic.jsonl` | 1.0 | 1.0 | 1.0 | 0.0 | L1–L3 pass; L4 fails grounding |

All eight pilot records pass state, tool-contract and trajectory checks, and all
have `false_completion: false`. The L4 judge explanations flag definitive causal
wording under the supplied grounding rubric. These are recorded judge results;
no agent correction or rubric adjustment was made in response.

The first authorized attempt produced local SDK errors: Anthropic SDK 1.13.0
rejects `temperature`. Only the judge adapter was corrected to omit it; an offline
regression test binds the adapter's request to the installed SDK signature.
The initial error reports are preserved as `*-semantic.jsonl`. Successful attempts
use `*-semantic-sdk-compatible.jsonl`. The judge uses provider-default sampling;
the agent's model configuration is unchanged. Initial error reports marked a
judge attempt before SDK validation; they contain no successful model score.

Results and input hashes are summarized in
`artifacts/evaluations/semantic-validation-summary.json`. The legacy pilot traces
were not rerun or modified.

Other limits: legacy state is reconstructed; legacy termination is inferred from
a final response and absence of a captured execution error; the tool schemas are
the fixed six-tool lab catalog; evidence-ID availability does not independently
establish causal support; no recursion-depth verification is possible from
atomic tool traces; tool-call limits are only checked when supplied in a reference;
Step Efficiency cannot be assessed from the available artifacts.
