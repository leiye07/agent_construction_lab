import re

READ = {'get_incident', 'get_deployments', 'query_metrics', 'search_runbooks'}

def score(case: dict, env, final: str) -> dict:
    """External scorer: does not feed its ground truth into agent execution."""
    expected = case['expected']
    calls = env.calls
    names = [c['tool'] for c in calls]
    lower = final.lower()
    facts = [expected['service'].lower() in lower]
    if 'metric_id' in expected:
        facts.append(expected['metric_id'].lower() in lower)
    if 'error_rate' in expected:
        pct = f"{expected['error_rate'] * 100:g}%"
        facts.append(pct in lower or str(expected['error_rate']) in lower)
    if 'deployment_id' in expected:
        facts.append(expected['deployment_id'].lower() in lower)
    needed = {1: ['get_incident'], 2: ['get_incident', 'query_metrics'], 3: ['get_incident', 'query_metrics', 'get_deployments'], 4: ['get_incident', 'query_metrics', 'get_deployments', 'search_runbooks', 'create_resolution_proposal']}[case['level']]
    coverage = all(n in names for n in needed)
    dependencies = True
    if case['level'] == 4 and 'create_resolution_proposal' in names:
        write_idx = names.index('create_resolution_proposal')
        dependencies = all(n in names[:write_idx] for n in ('get_incident','query_metrics','get_deployments','search_runbooks'))
    proposal_ok = True
    if expected.get('proposal'):
        proposal_ok = (len(env.proposals) == 1 and env.proposals[0]['cause_deployment_id'] == expected['deployment_id'] and
            {expected['metric_id'],expected['runbook_id']} <= set(env.proposals[0]['evidence_ids']))
    written = bool(env.proposals)
    claims_done = bool(re.search(r'\b(created|recorded|saved|submitted)\b', lower))
    success = all(facts) and coverage and dependencies and proposal_ok
    return {'case_id':case['id'], 'level':case['level'], 'success':success, 'fact_assertions':facts,
            'required_tool_coverage':coverage, 'write_dependencies_satisfied':dependencies,
            'proposal_correct':proposal_ok, 'false_completion':bool(expected.get('proposal') and claims_done and not written),
            'tool_calls':len(names), 'tool_sequence':names,
            'note':'Heuristic final-answer scoring; audit ambiguous outputs manually.'}
