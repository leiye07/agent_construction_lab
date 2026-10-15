import os
import pytest
from test_evaluator_calibration import CALIBRATION
from test_deterministic_evaluation import fixture
from agentlab.evaluation.contracts import ExecutionRecord, TaskReference
from agentlab.evaluation.semantic import semantic_checks, RUBRICS
from agentlab.evaluation.reporting import evaluate_record


def test_no_judge_is_explicitly_skipped():
    record, reference = fixture()
    checks = semantic_checks(record, reference)
    assert all(c.status == 'skipped' and c.score is None and c.passed is None for c in checks.values())
    report = evaluate_record(record, reference)
    assert report['claimed_action_completed'] is None
    assert report['false_completion'] is False  # completed write exists, regardless of claim
    assert report['overall_success'] is None


def test_rubrics_are_separate_and_versioned():
    assert set(RUBRICS) == {'grounding', 'answer_complete', 'claimed_action_completed'}
    assert 'Temporal correlation' in ' '.join(RUBRICS['grounding'])

@pytest.mark.semantic
@pytest.mark.parametrize('sample', [s for s in CALIBRATION if any(
    k in s['expected'] for k in ('grounding_pass', 'claimed_action_completed'))], ids=lambda s: s['scenario'])
def test_live_semantic_calibration(sample):
    judge = os.environ.get('LAB_JUDGE_MODEL', '')
    credential = 'ANTHROPIC_API_KEY' if judge.startswith('claude-') else 'OPENAI_API_KEY'
    if os.environ.get('LAB_RUN_SEMANTIC') != '1' or not os.environ.get(credential) or not judge:
        pytest.skip('Set LAB_RUN_SEMANTIC=1, provider API key and LAB_JUDGE_MODEL for actual judge calls')
    report = evaluate_record(ExecutionRecord.model_validate(sample['record']),
        TaskReference.model_validate(sample['reference']), os.environ['LAB_JUDGE_MODEL'])
    assert not report['evaluator_errors'], report['evaluator_errors']
    for field in ('grounding_pass', 'claimed_action_completed'):
        if field in sample['expected']:
            assert report[field] == sample['expected'][field], report['checks']
    if 'answer_complete' in sample['expected']:
        assert report['checks']['answer_complete']['passed'] == sample['expected']['answer_complete'], report['checks']
    if sample['scenario'] == 'claimed_write_without_state':
        assert report['false_completion'] is True
        assert report['overall_success'] is False


def test_anthropic_judge_request_matches_installed_sdk(monkeypatch):
    """Bind a real adapter request to the SDK signature without making a request."""
    import inspect
    from pydantic import SecretStr
    from deepeval.config.settings import get_settings
    from agentlab.evaluation.semantic import build_judge

    monkeypatch.setattr(get_settings(), 'ANTHROPIC_API_KEY', SecretStr('offline-no-network'))
    judge = build_judge('claude-sonnet-4-5-20250929')
    kwargs = judge._create_kwargs([{'type': 'text', 'text': 'API compatibility check'}], None)
    inspect.signature(judge.load_model().messages.create).bind(**kwargs)
