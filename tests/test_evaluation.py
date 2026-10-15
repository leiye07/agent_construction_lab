"""Compatibility fields no longer fabricate semantic success or completion claims."""
import pytest
from agentlab.environment import Environment, load_cases
from agentlab.evaluation import score

@pytest.mark.parametrize('index', [1, 2])
def test_readonly_completion_compatibility(index):
    case = load_cases()[index]
    env = Environment(case)
    env.get_incident(case['incident']['id'])
    env.query_metrics(case['incident']['service'])
    if index == 2:
        env.get_deployments(case['incident']['service'])
    result = score(case, env, 'Evidence recorded in a metric.')
    assert result['false_completion'] is False
    assert result['success'] is None
    assert result['fact_assertions'] is None
    assert result['required_tool_coverage'] is True
    assert result['execution_record']['state_source'] == 'snapshot'


def test_failed_write_without_judge_does_not_invent_claim():
    case = load_cases()[-1]
    result = score(case, Environment(case), 'Proposal successfully created.')
    assert result['success'] is False
    assert result['actual_action_completed'] is False
    assert result['claimed_action_completed'] is None
    assert result['false_completion'] is None
