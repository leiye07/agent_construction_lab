# Lab 5.1 — Tool Selection and Orchestration

A real model-driven agent with deterministic local tools, an independent DeepEval evaluation pipeline, and inspectable traces.

## Experiment contract

- **Independent variable:** task dependency depth (L1–L4).
- **Fixed agent:** one system prompt, one six-tool catalog, one model configuration, same code path.
- **Pilot:** four hand-authored cases. This is a validation pilot, **not** a statistically useful complexity study.
- **Next phase:** expand to balanced cases, repeated runs, and held-out cases after pilot validation.
- **Primary metric:** independently verified task outcomes; full success remains unknown until required semantic checks run.
- **Secondary:** missing tools, write prerequisites, final factual assertions, false completion, tool calls, duration.
- **Known limits:** see [EVALUATION.md](EVALUATION.md) for state reconstruction, semantic calibration, metric choices and unavailable trajectory evidence.

## Setup

Python 3.11+:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
python -m pytest -q
export OPENAI_API_KEY=... # set locally; do not commit credentials
python -m agentlab.runner --case all --model gpt-4.1-mini
```

To run a single case:

```bash
python -m agentlab.runner --case L3-a --output artifacts/l3.jsonl
```

To use Anthropic, set `ANTHROPIC_API_KEY` and select a `claude-*` model with
`--model` (or `LAB_MODEL`). The runner uses the
[LangChain Anthropic integration](https://docs.langchain.com/oss/python/integrations/chat/anthropic):

```bash
export ANTHROPIC_API_KEY= # set locally; do not commit credentials
python -m agentlab.runner --case all --model claude-sonnet-4-5-20250929 --output artifacts/anthropic.jsonl
```

Trace file: `artifacts/pilot.jsonl`. Every run starts with new environment state. The runner does not substitute a fake model output when credentials are absent. The configured model must support tool calling.

## Learner protocol

1. Review design and task invariants.
2. Run contract/evaluator tests.
3. Run the live pilot with the unchanged agent; preserve JSONL.
4. Choose a failing run. Inspect evidence first, not an automated root-cause suggestion.
5. Specify competing hypotheses and discriminating probes.
6. Direct Codex to implement **one approved change** and repeat the same runs.
7. Report improvements, regressions and limitations.

## Codex instructions

In investigation mode, instrument, reproduce and collect evidence only. Do not explain root cause or change behavior until the learner explicitly authorizes a hypothesis-driven correction. Keep baseline results immutable.

## Design limitations intentionally left for learner assessment

The baseline does not automatically verify semantic evidence support. It does not require a specific decision path, and it has no privileged evaluator inside the agent runtime. Decide whether these are acceptable for the first pilot before making production-grade claims.

## Evaluation framework

The evaluator now uses DeepEval 4.2.8 with deterministic state/contracts and opt-in GEval semantic judgments. Stored runs can be evaluated without rerunning the agent. See [EVALUATION.md](EVALUATION.md) for the architecture, compatibility changes, calibration status and commands.
