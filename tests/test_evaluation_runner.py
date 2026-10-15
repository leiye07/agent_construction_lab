import hashlib
import json
import sys
from pathlib import Path
import pytest
from agentlab.evaluation.runner import main
from test_deterministic_evaluation import fixture


def test_stored_pilot_evaluation_preserves_original(tmp_path, monkeypatch):
    source = Path('artifacts/anthropic.json')
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    destination = tmp_path / 'reports.jsonl'
    monkeypatch.setattr(sys, 'argv', ['evaluation', '--input', str(source), '--output', str(destination)])
    main()
    reports = [json.loads(line) for line in destination.read_text().splitlines()]
    assert len(reports) == 4
    assert all(r['state_correct'] and r['trajectory_valid'] and r['tool_contract_valid'] for r in reports)
    assert all(r['overall_success'] is None for r in reports)
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before
    with pytest.raises(SystemExit):
        main()


def test_normalized_record_and_adapter_error(tmp_path, monkeypatch):
    record, _ = fixture(0)
    source, dest = tmp_path / 'records.jsonl', tmp_path / 'reports.jsonl'
    source.write_text(json.dumps(record.model_dump()) + '\n' + json.dumps({'case_id': 'L2-a'}) + '\n5\n')
    monkeypatch.setattr(sys, 'argv', ['evaluation', '--input', str(source), '--output', str(dest)])
    main()
    reports = [json.loads(line) for line in dest.read_text().splitlines()]
    assert reports[0]['state_correct'] is True
    assert reports[1]['overall_success'] is None
    assert 'adapter' in reports[1]['evaluator_errors']
    assert reports[2]['case_id'] is None
    assert 'adapter' in reports[2]['evaluator_errors']


def test_independent_reference_contract_for_new_case_id(tmp_path, monkeypatch):
    record, reference = fixture(0)
    record.case_id = reference.case_id = 'reference-supplied-case'
    source, references, dest = tmp_path / 'record.jsonl', tmp_path / 'references.json', tmp_path / 'report.jsonl'
    source.write_text(json.dumps(record.model_dump()) + '\n')
    references.write_text(json.dumps([reference.model_dump()]))
    monkeypatch.setattr(sys, 'argv', ['evaluation', '--input', str(source), '--references', str(references), '--output', str(dest)])
    main()
    report = json.loads(dest.read_text())
    assert report['case_id'] == record.case_id
    assert report['state_correct'] is True
    assert not report['evaluator_errors']
