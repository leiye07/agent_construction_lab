import copy
import json
from pathlib import Path
import pytest
from agentlab.environment import load_cases
from agentlab.evaluation.adapters import record_from_legacy, reference_from_case
from agentlab.evaluation.deterministic import state_correctness, tool_contracts, trajectory_invariants
from agentlab.evaluation.reporting import evaluate_record


def fixture(index=3):
    case = load_cases()[index]
    raw = json.loads(Path('artifacts/anthropic.json').read_text())[index]
    return record_from_legacy(raw, case), reference_from_case(case)

@pytest.mark.parametrize('index', range(4))
def test_pilot_deterministic_checks(index):
    record, reference = fixture(index)
    report = evaluate_record(record, reference)
    assert report['state_correct']
    assert report['tool_contract_valid']
    assert report['trajectory_valid']
    assert report['grounding_score'] is None
    assert report['task_outcome_verified'] is None
    assert report['overall_success'] is None
    if index < 3:
        assert report['false_completion'] is False
    else:
        assert report['actual_action_completed'] is True
        assert report['claimed_action_completed'] is None

@pytest.mark.parametrize('field,value', [
    ('incident_id', 'wrong'), ('cause_deployment_id', 'wrong'),
    ('evidence_ids', ['MET-104']), ('evidence_ids', ['RB-104']),
])
def test_proposal_fields(field, value):
    record, reference = fixture()
    record.state_after['proposals'][0][field] = value
    assert not state_correctness(record, reference).passed

@pytest.mark.parametrize('change', ['duplicate', 'extra_state', 'readonly_write', 'unknown_state'])
def test_unexpected_or_missing_state(change):
    record, reference = fixture(0 if change == 'readonly_write' else 3)
    if change == 'duplicate':
        record.state_after['proposals'] *= 2
    elif change == 'extra_state':
        record.state_after['new_field'] = True
    elif change == 'readonly_write':
        record.state_after['proposals'].append({'id': 'unexpected'})
    else:
        record.state_after = None
    result = state_correctness(record, reference)
    assert result.passed is (None if change == 'unknown_state' else False)

@pytest.mark.parametrize('mutation', ['unknown_tool', 'missing_arg', 'bad_type', 'empty_id', 'bad_response', 'missing_result'])
def test_tool_contract_rejects_invalid_observations(mutation):
    record, _ = fixture(0)
    if mutation == 'unknown_tool':
        record.tool_calls[0].name = 'delete_service'
    elif mutation == 'missing_arg':
        record.tool_calls[0].arguments = {}
    elif mutation == 'bad_type':
        record.tool_calls[0].arguments['incident_id'] = 123
    elif mutation == 'empty_id':
        record.tool_calls[0].arguments['incident_id'] = ''
    elif mutation == 'bad_response':
        record.tool_results[0] = 'broken'
    else:
        record.tool_results = []
    assert tool_contracts(record).passed is False


def test_error_response_is_captured_without_becoming_evaluator_error():
    record, _ = fixture(0)
    record.tool_results[0] = {'error': 'not_found'}
    result = tool_contracts(record)
    assert result.passed
    assert result.metadata['tool_execution_errors'][0]['error'] == 'not_found'


def test_agent_exception_distinct_from_evaluator_failure():
    record, reference = fixture(0)
    record.execution_error = 'RuntimeError: agent failed'
    record.agent_terminated = False
    report = evaluate_record(record, reference)
    assert report['overall_success'] is False
    assert report['execution_error']
    assert not report['evaluator_errors']


def test_wrong_proposal_is_completed_action_but_incorrect_outcome():
    record, reference = fixture()
    record.state_after['proposals'][0]['cause_deployment_id'] = 'DEP-OTHER'
    report = evaluate_record(record, reference)
    assert report['state_correct'] is False
    assert report['actual_action_completed'] is True
    assert report['false_completion'] is False
    assert report['overall_success'] is False


def test_unavailable_state_does_not_become_completed_action():
    record, reference = fixture()
    record.state_after = None
    report = evaluate_record(record, reference)
    assert report['actual_action_completed'] is None
    assert report['false_completion'] is None
    assert report['overall_success'] is None

@pytest.mark.parametrize('index,result', [
    (0, {'id': 'WRONG', 'service': 'settlement-api', 'summary': 'test'}),
    (1, [{'id': 'MET-104', 'service': 'wrong-service', 'time': '16:10', 'error_rate': 0.25}]),
    (1, [{'id': 'MET-104', 'service': 'settlement-api', 'time': '16:10', 'error_rate': 1.2}]),
])
def test_response_must_match_tool_argument_and_metric_range(index, result):
    record, _ = fixture()
    record.tool_results[index] = result
    assert tool_contracts(record).passed is False


def test_malformed_write_arguments_report_failure_without_crash():
    record, reference = fixture()
    record.tool_calls[-1].arguments['evidence_ids'] = None
    assert not tool_contracts(record).passed
    assert not trajectory_invariants(record, reference).passed
