import sys
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from agentlab.environment import load_cases
from agentlab.runner import execute, main


@pytest.mark.parametrize('model_name,module,class_name', [
    ('gpt-4.1-mini', 'langchain_openai', 'ChatOpenAI'),
    ('claude-sonnet-4-5-20250929', 'langchain_anthropic', 'ChatAnthropic'),
])
def test_model_routing(model_name, module, class_name):
    constructor = Mock()
    agent = Mock()
    agent.invoke.return_value = {'messages': [SimpleNamespace(content='test response')]}
    with patch.dict(sys.modules, {module: SimpleNamespace(**{class_name: constructor})}), \
            patch('langchain.agents.create_agent', return_value=agent) as create_agent:
        result = execute(load_cases()[0], model_name)
    constructor.assert_called_once_with(model=model_name, temperature=0)
    assert create_agent.call_args.args[0] is constructor.return_value
    assert len(create_agent.call_args.args[1]) == 6
    assert result['model'] == model_name
    assert result['error'] is None


@pytest.mark.parametrize('model_name,key', [
    ('gpt-4.1-mini', 'OPENAI_API_KEY'),
    ('claude-sonnet-4-5-20250929', 'ANTHROPIC_API_KEY'),
])
def test_requires_selected_provider_key(model_name, key, capsys):
    with patch.dict('os.environ', {}, clear=True), \
            patch.object(sys, 'argv', ['runner', '--model', model_name]):
        with pytest.raises(SystemExit) as exc:
            main()
    assert exc.value.code == 2
    assert key in capsys.readouterr().err


def test_anthropic_cli_without_openai_key(tmp_path):
    output = tmp_path / 'trace.jsonl'
    with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'}, clear=True), \
            patch.object(sys, 'argv', ['runner', '--model', 'claude-test', '--case', 'L3-a', '--output', str(output)]), \
            patch('agentlab.runner.execute', return_value={'success': True, 'tool_calls': 0, 'error': None}) as run:
        main()
    assert run.call_count == 1
    assert run.call_args.args[1] == 'claude-test'
    assert output.exists()
