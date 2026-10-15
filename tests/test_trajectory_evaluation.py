import pytest
from test_deterministic_evaluation import fixture
from agentlab.evaluation.contracts import ToolInvocation
from agentlab.evaluation.deterministic import trajectory_invariants
from agentlab.evaluation.trajectory import tool_correctness

@pytest.mark.parametrize('order', [(0,1,2,3,4), (0,3,2,1,4), (3,2,1,0,4)])
def test_alternative_valid_orders(order):
    record, reference = fixture()
    record.tool_calls = [record.tool_calls[i] for i in order]
    record.tool_results = [record.tool_results[i] for i in order]
    assert trajectory_invariants(record, reference).passed
    result = tool_correctness(record, reference)
    assert result.passed, result.reason
    assert result.metadata['judge_invoked'] is False

@pytest.mark.parametrize('mutation', ['write_first', 'wrong_service', 'unseen_id', 'limit', 'unauthorized'])
def test_invalid_trajectories(mutation):
    record, reference = fixture()
    if mutation == 'write_first':
        record.tool_calls.insert(0, record.tool_calls.pop())
        record.tool_results.insert(0, record.tool_results.pop())
    elif mutation == 'wrong_service':
        record.tool_results[1] = []
    elif mutation == 'unseen_id':
        record.tool_calls[-1].arguments['evidence_ids'].append('FAKE')
    elif mutation == 'limit':
        reference.max_tool_calls = 4
    else:
        record.tool_calls.append(ToolInvocation(name='delete_service', arguments={}))
        record.tool_results.append({'error': 'denied'})
    assert not trajectory_invariants(record, reference).passed


def test_extra_allowed_lookup_does_not_require_exact_sequence():
    record, reference = fixture()
    record.tool_calls.insert(0, ToolInvocation(name='search_incidents', arguments={'service': 'settlement-api'}))
    record.tool_results.insert(0, [record.tool_results[0]])
    assert trajectory_invariants(record, reference).passed
    assert tool_correctness(record, reference).passed
