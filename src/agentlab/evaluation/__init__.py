"""Compatibility entry point; missing semantic judgments remain None."""
from .adapters import record_from_environment, reference_from_case
from .reporting import evaluate_record


def score(case, env, final, *, error=None, model='unknown', prompt=None):
    record = record_from_environment(case, env, final, error=error, model=model, prompt=prompt)
    report = evaluate_record(record, reference_from_case(case))
    report['execution_record'] = record.model_dump()
    names = [c['tool'] for c in env.calls]
    report.update(success=report['overall_success'], tool_calls=len(names), tool_sequence=names,
        required_tool_coverage=report['checks']['tool_correctness']['passed'],
        write_dependencies_satisfied=report['trajectory_valid'], proposal_correct=report['state_correct'],
        fact_assertions=None, note='Semantic checks skipped; success is unknown unless objectively failed.')
    return report
