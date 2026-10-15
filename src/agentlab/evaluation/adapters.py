"""Adapt original pilot artifacts without replaying or altering them."""
import copy
import json
import hashlib
from .contracts import ExecutionRecord, TaskReference, RequiredProposal, ToolInvocation

READ_TOOLS = ['get_incident', 'query_metrics', 'get_deployments', 'search_runbooks']
WRITE = 'create_resolution_proposal'

def reference_from_case(case):
    expected = case['expected']
    proposal = None
    if expected.get('proposal'):
        proposal = RequiredProposal(
            incident_id=case['incident']['id'],
            cause_deployment_id=expected['deployment_id'],
            evidence_ids=[expected['metric_id'], expected['runbook_id']],
        )
    return TaskReference(
        case_id=case['id'], objective=case['prompt'],
        expected_facts={k: v for k, v in expected.items() if k != 'proposal'},
        required_proposal=proposal,
        required_tools=READ_TOOLS[:case['level']] + ([WRITE] if proposal else []),
        write_dependencies={WRITE: READ_TOOLS} if proposal else {},
        prohibited_tools=[] if proposal else [WRITE],
    )

def record_from_legacy(raw, case):
    trace = raw.get('tool_trace')
    if trace is None:
        raise ValueError('tool_trace is required; aggregate scores cannot reconstruct execution')
    proposals = []
    for call in trace:
        result = call['result']
        if call['tool'] == WRITE and isinstance(result, dict) and result.get('status') == 'created':
            proposals.append({**copy.deepcopy(call['args']), 'id': result['proposal_id']})
    return ExecutionRecord(
        case_id=raw['case_id'], task_input=case['prompt'],
        agent_final_response=raw.get('final', ''),
        tool_calls=[ToolInvocation(name=c['tool'], arguments=c['args']) for c in trace],
        tool_results=[copy.deepcopy(c['result']) for c in trace],
        state_before={'proposals': []}, state_after={'proposals': proposals},
        state_source='reconstructed_from_tool_confirmations',
        execution_error=raw.get('error'), model_id=raw.get('model', 'unknown'),
        agent_terminated=bool(raw.get('final')) and not raw.get('error'),
    )

def record_from_environment(case, env, final, *, error=None, model='unknown', prompt=None):
    record = record_from_legacy({'case_id': case['id'], 'tool_trace': env.calls,
        'final': final, 'error': error, 'model': model}, case)
    record.state_after = {'proposals': copy.deepcopy(env.proposals)}
    record.state_source = 'snapshot'
    record.prompt_version = hashlib.sha256(prompt.encode()).hexdigest() if prompt else 'unknown'
    return record

def to_deepeval(record, reference):
    from deepeval.test_case import LLMTestCase, ToolCall
    return LLMTestCase(
        input=record.task_input, actual_output=record.agent_final_response,
        tools_called=[ToolCall(name=c.name, input_parameters=c.arguments, output=r)
            for c, r in zip(record.tool_calls, record.tool_results)],
        expected_tools=[ToolCall(name=n) for n in reference.required_tools],
        context=[json.dumps(r, sort_keys=True) for r in record.tool_results],
        expected_output=reference.reference_answer,
    )
