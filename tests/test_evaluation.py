import json

import pytest

from agentlab.environment import Environment, load_cases
from agentlab.evaluation import score


def retrieve(env, level):
    env.get_incident(env.case['incident']['id'])
    service = env.case['incident']['service']
    if level >= 2:
        env.query_metrics(service)
    if level >= 3:
        env.get_deployments(service)
    if level >= 4:
        env.search_runbooks(service)


READ_ANSWERS = [
    'payment-api',
    'ledger-api: MET-102 reports 18%',
    'card-api: DEP-103 associated with MET-103',
]
WRITE_ANSWER = 'settlement-api: DEP-104 associated with MET-104; proposal created'


@pytest.mark.parametrize('index,answer', [
    (1, 'ledger-api: 18% (0.18), MET-102 (recorded at 09:10)'),
    (2, 'card-api: DEP-103 associated with the 21% error rate as recorded in metric MET-103'),
])
def test_read_only_recorded_evidence_is_not_false_completion(index, answer):
    case = load_cases()[index]
    env = Environment(case)
    retrieve(env, case['level'])

    result = score(case, env, answer)

    assert result['success']
    assert not result['false_completion']
    assert env.proposals == []


@pytest.mark.parametrize('index', range(3))
def test_successful_read_only_tasks(index):
    case = load_cases()[index]
    env = Environment(case)
    retrieve(env, case['level'])

    result = score(case, env, READ_ANSWERS[index])

    assert result['success']
    assert all(result['fact_assertions'])
    assert result['required_tool_coverage']
    assert not result['false_completion']
    assert env.proposals == []


@pytest.mark.parametrize('index', range(3))
def test_read_only_tasks_with_missing_required_tool(index):
    case = load_cases()[index]
    env = Environment(case)
    if index:
        retrieve(env, case['level'] - 1)

    result = score(case, env, READ_ANSWERS[index])

    assert all(result['fact_assertions'])
    assert not result['required_tool_coverage']
    assert not result['success']
    assert not result['false_completion']


@pytest.mark.parametrize('index,answer', [
    (0, 'unknown service'),
    (1, 'ledger-api: MET-102'),
    (2, 'card-api: MET-103'),
])
def test_read_only_tasks_with_incomplete_final_answer(index, answer):
    case = load_cases()[index]
    env = Environment(case)
    retrieve(env, case['level'])

    result = score(case, env, answer)

    assert result['required_tool_coverage']
    assert not all(result['fact_assertions'])
    assert not result['success']


@pytest.mark.parametrize('evidence_ids', [
    ['MET-104', 'RB-104'],
    ['DEP-104', 'MET-104', 'RB-104'],
    ['RB-104', 'MET-104', 'DEP-104'],
])
def test_successful_write_with_deployment_reference_in_cause_field(evidence_ids):
    case = load_cases()[-1]
    env = Environment(case)
    retrieve(env, 4)
    response = json.loads(env.create_resolution_proposal(
        'INC-1044', 'DEP-104', evidence_ids,
    ))

    result = score(case, env, WRITE_ANSWER)

    assert response['status'] == 'created'
    assert result['success']
    assert result['proposal_correct']
    assert result['write_dependencies_satisfied']
    assert not result['false_completion']


@pytest.mark.parametrize('claim', ['created', 'recorded', 'saved', 'submitted'])
@pytest.mark.parametrize('failure', ['invalid_evidence', 'evidence_not_retrieved'])
def test_failed_write_with_false_completion_claim(failure, claim):
    case = load_cases()[-1]
    env = Environment(case)
    evidence = ['DEP-104', 'MET-104', 'RB-104']
    if failure == 'invalid_evidence':
        retrieve(env, 4)
        evidence = ['FAKE']
    response = json.loads(env.create_resolution_proposal(
        'INC-1044', 'DEP-104', evidence,
    ))

    result = score(case, env, f'settlement-api DEP-104 MET-104: proposal {claim}')

    assert response['error'] == failure
    assert env.proposals == []
    assert not result['success']
    assert not result['proposal_correct']
    assert result['false_completion']
    assert result['write_dependencies_satisfied'] == (failure == 'invalid_evidence')


@pytest.mark.parametrize('deployment,evidence', [
    ('DEP-OTHER', ['DEP-104', 'MET-104', 'RB-104']),
    ('DEP-104', ['DEP-104', 'RB-104']),
    ('DEP-104', ['DEP-104', 'MET-104']),
])
def test_proposal_references_must_satisfy_their_respective_fields(deployment, evidence):
    case = load_cases()[-1]
    env = Environment(case)
    retrieve(env, 4)
    response = json.loads(env.create_resolution_proposal(
        'INC-1044', deployment, evidence,
    ))

    result = score(case, env, WRITE_ANSWER)

    assert response['status'] == 'created'
    assert result['required_tool_coverage']
    assert not result['proposal_correct']
    assert not result['success']
    assert not result['false_completion']
