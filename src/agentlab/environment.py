import copy
import json
from dataclasses import dataclass, field
from pathlib import Path

DATA = Path(__file__).resolve().parents[2] / 'data' / 'cases.json'

@dataclass
class Environment:
    case: dict
    proposals: list[dict] = field(default_factory=list)
    calls: list[dict] = field(default_factory=list)

    def _call(self, name, args, response):
        self.calls.append({'tool': name, 'args': copy.deepcopy(args), 'result': copy.deepcopy(response)})
        return json.dumps(response, sort_keys=True)

    def search_incidents(self, service: str):
        incidents = [self.case['incident']] if self.case['incident']['service'] == service else []
        return self._call('search_incidents', {'service': service}, incidents)

    def get_incident(self, incident_id: str):
        result = self.case['incident'] if incident_id == self.case['incident']['id'] else {'error': 'not_found'}
        return self._call('get_incident', {'incident_id': incident_id}, result)

    def get_deployments(self, service: str):
        result = self.case['deployments'] if service == self.case['incident']['service'] else []
        return self._call('get_deployments', {'service': service}, result)

    def query_metrics(self, service: str):
        result = self.case['metrics'] if service == self.case['incident']['service'] else []
        return self._call('query_metrics', {'service': service}, result)

    def search_runbooks(self, service: str):
        result = self.case['runbooks'] if service == self.case['incident']['service'] else []
        return self._call('search_runbooks', {'service': service}, result)

    def create_resolution_proposal(self, incident_id: str, cause_deployment_id: str, evidence_ids: list[str]):
        args = {'incident_id': incident_id, 'cause_deployment_id': cause_deployment_id, 'evidence_ids': evidence_ids}
        valid_ids = {x['id'] for group in ('metrics', 'deployments', 'runbooks') for x in self.case[group]}
        if incident_id != self.case['incident']['id']:
            result = {'error': 'unknown_incident'}
        elif not evidence_ids or not set(evidence_ids) <= valid_ids:
            result = {'error': 'invalid_evidence'}
        elif cause_deployment_id not in {x['id'] for x in self.case['deployments']}:
            result = {'error': 'unknown_deployment'}
        elif not {'get_incident', 'get_deployments', 'query_metrics', 'search_runbooks'} <= {c['tool'] for c in self.calls}:
            result = {'error': 'evidence_not_retrieved'}
        elif any(x['incident_id'] == incident_id for x in self.proposals):
            result = {'error': 'duplicate_proposal'}
        else:
            proposal = dict(args, id=f'PROP-{len(self.proposals)+1}')
            self.proposals.append(proposal)
            result = {'status': 'created', 'proposal_id': proposal['id']}
        return self._call('create_resolution_proposal', args, result)


def load_cases():
    return json.loads(DATA.read_text())
