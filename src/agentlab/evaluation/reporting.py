from importlib.metadata import version, PackageNotFoundError
from .contracts import EVALUATOR_VERSION, RUBRIC_VERSION, CheckResult
from .deterministic import state_correctness, tool_contracts, trajectory_invariants
from .trajectory import tool_correctness
from .semantic import semantic_checks


def combine(values):
    if any(v is False for v in values):
        return False
    return True if all(v is True for v in values) else None


def evaluate_record(record, reference, judge_model=None):
    if record.case_id != reference.case_id:
        raise ValueError('Execution and reference case IDs differ')
    checks = {'state': state_correctness(record, reference),
        'tool_contract': tool_contracts(record),
        'trajectory': trajectory_invariants(record, reference),
        'tool_correctness': tool_correctness(record, reference)}
    checks.update(semantic_checks(record, reference, judge_model))
    checks['step_efficiency'] = CheckResult(status='unavailable',
        reason='Pilot records contain atomic tool calls, not complete agent/LLM spans required by StepEfficiencyMetric')
    state = checks['state'].passed
    actual = False
    if reference.required_proposal:
        if record.state_before is None or record.state_after is None:
            actual = None
        elif not isinstance(record.state_before.get('proposals'), list) or not isinstance(record.state_after.get('proposals'), list):
            actual = None
        else:
            actual = any(isinstance(p, dict) and p not in record.state_before['proposals']
                and p.get('incident_id') == reference.required_proposal.incident_id
                for p in record.state_after['proposals'])
    claim = checks.get('claimed_action_completed')
    claimed = (claim.score >= 0.8 if claim and claim.score is not None else None) if reference.required_proposal else False
    false_completion = combine([claimed, None if actual is None else not actual]) if reference.required_proposal else False
    completion = False if false_completion else (None if false_completion is None else True)
    outcome = combine([state, checks['answer_complete'].passed])
    overall = combine([outcome, checks['tool_contract'].passed, checks['trajectory'].passed,
        checks['tool_correctness'].passed, checks['grounding'].passed, completion,
        record.execution_error is None, record.agent_terminated])
    try:
        framework_version = version('deepeval')
    except PackageNotFoundError:
        framework_version = None
    return {'case_id': record.case_id, 'evaluator_version': EVALUATOR_VERSION,
        'deepeval_version': framework_version, 'rubric_version': RUBRIC_VERSION,
        'judge_model': judge_model, 'prompt_version': record.prompt_version, 'model_id': record.model_id,
        'state_source': record.state_source, 'state_correct': state,
        'tool_contract_valid': checks['tool_contract'].passed,
        'trajectory_valid': checks['trajectory'].passed,
        'grounding_score': checks['grounding'].score, 'grounding_pass': checks['grounding'].passed,
        'agent_terminated': record.agent_terminated, 'task_outcome_verified': outcome,
        'claimed_action_completed': claimed, 'actual_action_completed': actual,
        'false_completion': false_completion, 'overall_success': overall,
        'execution_error': record.execution_error,
        'evaluator_errors': {k: v.reason for k, v in checks.items() if v.status == 'error'},
        'checks': {k: v.model_dump() for k, v in checks.items()}}
