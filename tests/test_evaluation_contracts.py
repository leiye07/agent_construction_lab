import copy
import json
from pathlib import Path
import pytest
from pydantic import ValidationError
from agentlab.environment import load_cases
from agentlab.evaluation.adapters import record_from_legacy, reference_from_case
from agentlab.evaluation.contracts import ExecutionRecord

@pytest.fixture
def pilot():
    return json.loads(Path('artifacts/anthropic.json').read_text())

def test_legacy_adapter_preserves_observations(pilot):
    before = copy.deepcopy(pilot)
    for case, raw in zip(load_cases(), pilot):
        record = record_from_legacy(raw, case)
        assert ExecutionRecord.model_validate(record.model_dump()) == record
        assert record.state_source == 'reconstructed_from_tool_confirmations'
        assert record.agent_final_response == raw['final']
        assert record.tool_results == [c['result'] for c in raw['tool_trace']]
    assert pilot == before

def test_missing_trace_is_not_empty_execution():
    with pytest.raises(ValueError, match='tool_trace'):
        record_from_legacy({'case_id': 'L1-a'}, load_cases()[0])

def test_reference_distinct_from_observation(pilot):
    case = load_cases()[-1]
    reference = reference_from_case(case)
    record = record_from_legacy(pilot[-1], case)
    assert reference.required_proposal.cause_deployment_id not in reference.required_proposal.evidence_ids
    assert 'expected_facts' not in record.model_dump()
    with pytest.raises(ValidationError):
        ExecutionRecord.model_validate({**record.model_dump(), 'expected_facts': {}})
