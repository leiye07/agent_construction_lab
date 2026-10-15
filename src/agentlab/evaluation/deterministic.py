"""Objective state, schema and execution checks; no model or answer parsing."""
from pydantic import BaseModel, ConfigDict, StrictStr, ValidationError
from .contracts import CheckResult, check
from .adapters import WRITE

class Arguments(BaseModel):
    model_config = ConfigDict(extra='forbid')
class ServiceArgs(Arguments):
    service: StrictStr
class IncidentArgs(Arguments):
    incident_id: StrictStr
class ProposalArgs(IncidentArgs):
    cause_deployment_id: StrictStr
    evidence_ids: list[StrictStr]

SCHEMAS = {'search_incidents': ServiceArgs, 'get_incident': IncidentArgs,
    'get_deployments': ServiceArgs, 'query_metrics': ServiceArgs,
    'search_runbooks': ServiceArgs, WRITE: ProposalArgs}
RECORD_FIELDS = {
    'search_incidents': {'id': str, 'service': str, 'summary': str},
    'get_incident': {'id': str, 'service': str, 'summary': str},
    'get_deployments': {'id': str, 'service': str, 'time': str, 'change': str},
    'query_metrics': {'id': str, 'service': str, 'time': str, 'error_rate': (int, float)},
    'search_runbooks': {'id': str, 'service': str, 'steps': str},
}

def valid_response(name, result):
    if isinstance(result, dict) and 'error' in result:
        return isinstance(result['error'], str) and bool(result['error'])
    if name == WRITE:
        return isinstance(result, dict) and result.get('status') == 'created' and isinstance(result.get('proposal_id'), str)
    rows = [result] if name == 'get_incident' else result
    if not isinstance(rows, list):
        return False
    return all(isinstance(row, dict) and all(
        key in row and isinstance(row[key], kind) and not isinstance(row[key], bool)
        for key, kind in RECORD_FIELDS[name].items()) for row in rows)

def tool_contracts(record):
    issues, execution_errors = [], []
    if len(record.tool_calls) != len(record.tool_results):
        issues.append('tool call/result count mismatch')
    for i, (call, result) in enumerate(zip(record.tool_calls, record.tool_results)):
        schema = SCHEMAS.get(call.name)
        if schema is None:
            issues.append(f'{i}: unrecognized tool {call.name}')
            continue
        try:
            parsed = schema.model_validate(call.arguments)
            if any(isinstance(v, str) and not v.strip() for v in parsed.model_dump().values()):
                issues.append(f'{i}: empty required identifier')
            if call.name == WRITE and any(not v.strip() for v in parsed.evidence_ids):
                issues.append(f'{i}: empty evidence identifier')
        except ValidationError as exc:
            issues.append(f'{i}: invalid arguments: {exc}')
        if not valid_response(call.name, result):
            issues.append(f'{i}: invalid response')
        elif call.name in RECORD_FIELDS and not (isinstance(result, dict) and 'error' in result):
            rows = [result] if call.name == 'get_incident' else result
            for row in rows:
                if any(isinstance(v, str) and not v.strip() for v in row.values()):
                    issues.append(f'{i}: empty response field')
                if call.name == 'get_incident' and row['id'] != call.arguments.get('incident_id'):
                    issues.append(f'{i}: incident response does not match requested identifier')
                if call.name != 'get_incident' and row['service'] != call.arguments.get('service'):
                    issues.append(f'{i}: response does not match requested service')
                if call.name == 'query_metrics' and not 0 <= row['error_rate'] <= 1:
                    issues.append(f'{i}: invalid error rate')
        if isinstance(result, dict) and 'error' in result:
            execution_errors.append({'index': i, 'tool': call.name, 'error': result['error']})
    value = check(not issues, '; '.join(issues) or 'All tool schemas and responses valid')
    value.metadata['tool_execution_errors'] = execution_errors
    return value

def state_correctness(record, reference):
    if record.state_before is None or record.state_after is None:
        return CheckResult(status='unavailable', reason='State snapshots unavailable')
    before, after = record.state_before, record.state_after
    if not isinstance(before.get('proposals'), list) or not isinstance(after.get('proposals'), list):
        return CheckResult(status='error', reason='Malformed proposal state')
    if reference.required_proposal is None:
        return check(after == before, 'Read-only task must leave state unchanged')
    wanted = reference.required_proposal
    old, proposals = before['proposals'], after['proposals']
    new = [p for p in proposals if p not in old]
    ok = (len(new) == 1 and len(proposals) == len(old) + 1 and all(p in proposals for p in old)
        and all(after.get(k) == v for k, v in before.items() if k != 'proposals')
        and set(after) == set(before))
    if ok:
        p = new[0]
        ok = (isinstance(p, dict) and p.get('incident_id') == wanted.incident_id
            and p.get('cause_deployment_id') == wanted.cause_deployment_id
            and isinstance(p.get('evidence_ids'), list)
            and all(isinstance(v, str) for v in p['evidence_ids'])
            and set(wanted.evidence_ids) <= set(p['evidence_ids'])
            and set(p) <= {'id', 'incident_id', 'cause_deployment_id', 'evidence_ids'})
    return check(ok, 'Required proposal fields and absence of unexpected state changes checked')

def trajectory_invariants(record, reference):
    issues, available, successful_tools = [], set(), set()
    if len(record.tool_calls) != len(record.tool_results):
        issues.append('Incomplete tool results')
    if reference.max_tool_calls is not None and len(record.tool_calls) > reference.max_tool_calls:
        issues.append('Tool call limit exceeded')
    for i, (call, result) in enumerate(zip(record.tool_calls, record.tool_results)):
        if call.name not in SCHEMAS or call.name in reference.prohibited_tools:
            issues.append(f'{i}: unauthorized tool attempt {call.name}')
        if call.name in reference.write_dependencies:
            missing = set(reference.write_dependencies[call.name]) - successful_tools
            if missing:
                issues.append(f'{i}: missing successful evidence tools {sorted(missing)}')
            evidence = call.arguments.get('evidence_ids', [])
            ids = list(evidence) if isinstance(evidence, list) else [None]
            ids += [call.arguments.get('cause_deployment_id'), call.arguments.get('incident_id')]
            if any(not isinstance(v, str) or v not in available for v in ids):
                issues.append(f'{i}: referenced evidence unavailable before write')
        if call.name in SCHEMAS and valid_response(call.name, result) and not (isinstance(result, dict) and 'error' in result):
            rows = result if isinstance(result, list) else [result]
            if rows:
                successful_tools.add(call.name)
            for row in rows:
                if isinstance(row, dict) and isinstance(row.get('id'), str):
                    available.add(row['id'])
    missing = set(reference.required_tools) - successful_tools
    if missing:
        issues.append(f'Missing successful required tools: {sorted(missing)}')
    result = check(not issues, '; '.join(issues) or 'Dependencies and permissions satisfied; order unrestricted otherwise')
    result.metadata['max_tool_calls'] = reference.max_tool_calls
    return result
