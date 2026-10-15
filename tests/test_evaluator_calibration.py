import json
from pathlib import Path
import pytest
from agentlab.evaluation.contracts import ExecutionRecord, TaskReference
from agentlab.evaluation.reporting import evaluate_record

CALIBRATION = json.loads((Path(__file__).parent / 'calibration/cases.json').read_text())

@pytest.mark.parametrize('sample', CALIBRATION, ids=lambda s: s['scenario'])
def test_deterministic_calibration(sample):
    record = ExecutionRecord.model_validate(sample['record'])
    reference = TaskReference.model_validate(sample['reference'])
    report = evaluate_record(record, reference)
    for field in ('state_correct', 'trajectory_valid', 'tool_contract_valid', 'overall_success'):
        if field in sample['expected']:
            assert report[field] == sample['expected'][field], report
    assert report['grounding_score'] is None
    assert report['checks']['grounding']['status'] == 'skipped'
    assert not report['evaluator_errors']
