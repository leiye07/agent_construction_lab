# Lab 5.1 — Tool Selection and Orchestration

A real model-driven agent with deterministic local tools, an independent task evaluator, and inspectable traces.

## Experiment contract

- **Independent variable:** task dependency depth (L1–L4).
- **Fixed agent:** one system prompt, one six-tool catalog, one model configuration, same code path.
- **Pilot:** four hand-authored cases. This is a validation pilot, **not** a statistically useful complexity study.
- **Next phase:** expand to balanced cases, repeated runs, and held-out cases after pilot validation.
- **Primary metric:** verified task success, including external state for writes.
- **Secondary:** missing tools, write prerequisites, final factual assertions, false completion, tool calls, duration.
- **Known limits:** final-answer evaluator uses transparent heuristics; trajectory coverage is coarse; scenario fixtures are tiny and all evidence is unambiguous; current write guard checks that required evidence tools were invoked and IDs exist, but not that specific evidence IDs were returned by those invocations or that they support the conclusion. Do not overclaim. `false_completion` currently detects asserted writes only, not all kinds of premature termination.

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
