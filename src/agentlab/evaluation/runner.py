"""Evaluate stored observations; never invokes the task agent."""
import argparse
import json
from pathlib import Path
from agentlab.environment import load_cases
from .contracts import ExecutionRecord, TaskReference
from .adapters import record_from_legacy, reference_from_case
from .reporting import evaluate_record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--references', help='JSON array of separate TaskReference contracts; defaults to lab fixtures')
    parser.add_argument('--judge-model', help='Opt-in DeepEval judge; requires matching OpenAI or Anthropic credentials')
    args = parser.parse_args()
    source, destination = Path(args.input), Path(args.output)
    if source.resolve() == destination.resolve() or destination.exists():
        parser.error('Output must be a new file; original artifacts are immutable')
    text = source.read_text()
    rows = json.loads(text) if text.lstrip().startswith('[') else [json.loads(line) for line in text.splitlines() if line.strip()]
    references = {r.case_id: r for r in (
        [TaskReference.model_validate(r) for r in json.loads(Path(args.references).read_text())]
        if args.references else [reference_from_case(c) for c in load_cases()])}
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('x') as stream:
        for raw in rows:
            try:
                sample = raw if 'record' in raw and 'reference' in raw else None
                if sample:
                    raw = sample['record']
                reference = TaskReference.model_validate(sample['reference']) if sample else references[raw['case_id']]
                if 'execution_record' in raw:
                    record = ExecutionRecord.model_validate(raw['execution_record'])
                else:
                    record = ExecutionRecord.model_validate(raw) if 'agent_final_response' in raw else record_from_legacy(raw, {'prompt': reference.objective})
                report = evaluate_record(record, reference, args.judge_model)
                if sample:
                    report['scenario'] = sample['scenario']
                    report['reference_labels'] = sample['expected']
                    report['label_source'] = sample['label_source']
                    report['calibration_disagreements'] = {}
                    report['calibration_unavailable'] = []
                    for field, expected in sample['expected'].items():
                        observed = report['checks']['answer_complete']['passed'] if field == 'answer_complete' else report.get(field)
                        if observed is None:
                            report['calibration_unavailable'].append(field)
                        elif observed != expected:
                            report['calibration_disagreements'][field] = {'expected': expected, 'observed': observed}
            except Exception as exc:
                report = {'case_id': raw.get('case_id') if isinstance(raw, dict) else None, 'overall_success': None,
                    'evaluator_errors': {'adapter': f'{type(exc).__name__}: {exc}'}}
            stream.write(json.dumps(report) + '\n')
            print(f"{report['case_id']}: overall_success={report['overall_success']}")

if __name__ == '__main__':
    main()
