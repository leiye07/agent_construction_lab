import json
import unittest
from agentlab.environment import Environment,load_cases
from agentlab.evaluation import score

class TestLab(unittest.TestCase):
    def test_case_data(self):
        cases=load_cases()
        self.assertEqual([x['level'] for x in cases],[1,2,3,4])
        self.assertEqual(len({x['id'] for x in cases}),len(cases))
    def test_tools_and_write_guard(self):
        c=load_cases()[-1]; e=Environment(c)
        self.assertEqual(json.loads(e.get_incident('INC-1044'))['service'],'settlement-api')
        self.assertEqual(json.loads(e.create_resolution_proposal('INC-1044','DEP-104',['FAKE']))['error'],'invalid_evidence')
        self.assertEqual(len(e.proposals),0)
        self.assertEqual(json.loads(e.create_resolution_proposal('INC-1044','DEP-104',['DEP-104','MET-104','RB-104']))['error'],'evidence_not_retrieved')
        e.get_incident('INC-1044'); e.get_deployments('settlement-api'); e.query_metrics('settlement-api'); e.search_runbooks('settlement-api')
        ok=json.loads(e.create_resolution_proposal('INC-1044','DEP-104',['DEP-104','MET-104','RB-104']))
        self.assertEqual(ok['status'],'created')
        self.assertEqual(json.loads(e.create_resolution_proposal('INC-1044','DEP-104',['DEP-104']))['error'],'duplicate_proposal')
    def test_evaluator_positive_and_negative(self):
        c=load_cases()[-1]; e=Environment(c)
        e.get_incident('INC-1044'); e.query_metrics('settlement-api'); e.get_deployments('settlement-api'); e.search_runbooks('settlement-api')
        e.create_resolution_proposal('INC-1044','DEP-104',['DEP-104','MET-104','RB-104'])
        good=score(c,e,'settlement-api: DEP-104 associated with MET-104, proposal created')
        self.assertIsNone(good['success'])
        self.assertTrue(good['state_correct'])
        self.assertFalse(good['false_completion'])
        e2=Environment(c)
        bad=score(c,e2,'settlement-api DEP-104 MET-104: proposal created')
        self.assertFalse(bad['success'])
        self.assertIsNone(bad['false_completion'])
        self.assertFalse(bad['actual_action_completed'])
    def test_external_state_reset(self):
        c=load_cases()[-1]
        a,b=Environment(c),Environment(c)
        a.create_resolution_proposal('INC-1044','DEP-104',['DEP-104'])
        self.assertEqual(len(b.proposals),0)

if __name__=='__main__': unittest.main()
