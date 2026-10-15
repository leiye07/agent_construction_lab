"""DeepEval unordered tool coverage, with structured invariants kept separate."""
from .contracts import CheckResult
from .adapters import to_deepeval


def tool_correctness(record, reference):
    try:
        from deepeval.metrics import ToolCorrectnessMetric
        from deepeval.models import DeepEvalBaseLLM

        class NoJudge(DeepEvalBaseLLM):
            """No fabricated responses: fail if a deterministic metric requests a judge."""
            def load_model(self):
                return self
            def generate(self, *args, **kwargs):
                raise RuntimeError('Judge invocation forbidden for deterministic tool coverage')
            async def a_generate(self, *args, **kwargs):
                return self.generate(*args, **kwargs)
            def get_model_name(self):
                return 'deterministic-no-judge'

        metric = ToolCorrectnessMetric(
            model=NoJudge(), threshold=1, async_mode=False,
            should_consider_ordering=False, should_exact_match=False,
        )
        metric.measure(to_deepeval(record, reference), _show_indicator=False)
        ok = metric.is_successful()
        return CheckResult(status='passed' if ok else 'failed', passed=ok,
            score=metric.score, reason=metric.reason,
            metadata={'metric': 'ToolCorrectnessMetric', 'judge_invoked': False})
    except Exception as exc:
        return CheckResult(status='error', reason=f'{type(exc).__name__}: {exc}')
