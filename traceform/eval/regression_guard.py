import logging
from typing import Any, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class RegressionCheck(BaseModel):
    metric: str
    current_value: float
    baseline_value: float
    difference: float
    threshold: float
    passed: bool
    reason: str


class RegressionReport(BaseModel):
    has_regressed: bool
    checks: list[RegressionCheck] = Field(default_factory=list)
    summary: str = ""


class RegressionGuard:
    """
    §6C — Regression Detection Engine.
    Compares current evaluation run metrics against the previous baseline run.
    Fails when:
      - Accuracy drop > 3% (0.03)
      - Hallucination increase > 2% (0.02)
      - Citation coverage < 95% (0.95)
      - Latency increase > 25% (0.25)
      - Cost increase > 50% (0.50)
    """

    ACCURACY_DROP_THRESHOLD = 0.03
    HALLUCINATION_INCREASE_THRESHOLD = 0.02
    MIN_CITATION_COVERAGE = 0.95
    LATENCY_INCREASE_THRESHOLD = 0.25
    COST_INCREASE_THRESHOLD = 0.50

    @classmethod
    def evaluate(
        cls,
        current_metrics: dict[str, float],
        baseline_metrics: Optional[dict[str, float]] = None,
    ) -> RegressionReport:
        checks: list[RegressionCheck] = []
        has_regressed = False

        curr_acc = current_metrics.get("fact_accuracy", 1.0)
        curr_halluc = current_metrics.get("hallucination_rate", 0.0)
        curr_cit = current_metrics.get("citation_coverage", 1.0)
        curr_lat = current_metrics.get("avg_latency", 4000.0)
        curr_cost = current_metrics.get("avg_cost", 0.01)

        # 1. Absolute citation coverage gate
        cit_pass = curr_cit >= cls.MIN_CITATION_COVERAGE
        checks.append(
            RegressionCheck(
                metric="citation_coverage",
                current_value=curr_cit,
                baseline_value=baseline_metrics.get("citation_coverage", 1.0) if baseline_metrics else 1.0,
                difference=round(curr_cit - (baseline_metrics.get("citation_coverage", 1.0) if baseline_metrics else 1.0), 4),
                threshold=cls.MIN_CITATION_COVERAGE,
                passed=cit_pass,
                reason=f"Citation coverage ({curr_cit*100:.1f}%) meets >= {cls.MIN_CITATION_COVERAGE*100}% threshold."
                if cit_pass
                else f"Citation coverage ({curr_cit*100:.1f}%) is below mandatory {cls.MIN_CITATION_COVERAGE*100}% floor.",
            )
        )
        if not cit_pass:
            has_regressed = True

        if baseline_metrics:
            base_acc = baseline_metrics.get("fact_accuracy", curr_acc)
            base_halluc = baseline_metrics.get("hallucination_rate", curr_halluc)
            base_lat = baseline_metrics.get("avg_latency", curr_lat)
            base_cost = baseline_metrics.get("avg_cost", curr_cost)

            # 2. Accuracy drop
            acc_diff = base_acc - curr_acc
            acc_pass = acc_diff <= cls.ACCURACY_DROP_THRESHOLD
            checks.append(
                RegressionCheck(
                    metric="fact_accuracy",
                    current_value=curr_acc,
                    baseline_value=base_acc,
                    difference=round(curr_acc - base_acc, 4),
                    threshold=cls.ACCURACY_DROP_THRESHOLD,
                    passed=acc_pass,
                    reason=f"Accuracy ({curr_acc*100:.1f}%) within allowable drop limit (baseline: {base_acc*100:.1f}%)."
                    if acc_pass
                    else f"Accuracy dropped by {acc_diff*100:.1f}% (exceeds {cls.ACCURACY_DROP_THRESHOLD*100}% limit).",
                )
            )
            if not acc_pass:
                has_regressed = True

            # 3. Hallucination increase
            halluc_diff = curr_halluc - base_halluc
            halluc_pass = halluc_diff <= cls.HALLUCINATION_INCREASE_THRESHOLD
            checks.append(
                RegressionCheck(
                    metric="hallucination_rate",
                    current_value=curr_halluc,
                    baseline_value=base_halluc,
                    difference=round(halluc_diff, 4),
                    threshold=cls.HALLUCINATION_INCREASE_THRESHOLD,
                    passed=halluc_pass,
                    reason=f"Hallucination rate ({curr_halluc*100:.1f}%) acceptable."
                    if halluc_pass
                    else f"Hallucination rate increased by {halluc_diff*100:.1f}% (exceeds {cls.HALLUCINATION_INCREASE_THRESHOLD*100}% limit).",
                )
            )
            if not halluc_pass:
                has_regressed = True

            # 4. Latency increase
            if base_lat > 0:
                lat_increase_pct = (curr_lat - base_lat) / base_lat
                lat_pass = lat_increase_pct <= cls.LATENCY_INCREASE_THRESHOLD
                checks.append(
                    RegressionCheck(
                        metric="avg_latency",
                        current_value=curr_lat,
                        baseline_value=base_lat,
                        difference=round(curr_lat - base_lat, 2),
                        threshold=cls.LATENCY_INCREASE_THRESHOLD,
                        passed=lat_pass,
                        reason=f"Latency ({curr_lat:.0f}ms) within allowable growth."
                        if lat_pass
                        else f"Latency grew by {lat_increase_pct*100:.1f}% (exceeds {cls.LATENCY_INCREASE_THRESHOLD*100}% limit).",
                    )
                )
                if not lat_pass:
                    has_regressed = True

            # 5. Cost increase
            if base_cost > 0:
                cost_increase_pct = (curr_cost - base_cost) / base_cost
                cost_pass = cost_increase_pct <= cls.COST_INCREASE_THRESHOLD
                checks.append(
                    RegressionCheck(
                        metric="avg_cost",
                        current_value=curr_cost,
                        baseline_value=base_cost,
                        difference=round(curr_cost - base_cost, 4),
                        threshold=cls.COST_INCREASE_THRESHOLD,
                        passed=cost_pass,
                        reason=f"Cost (${curr_cost:.4f}) within allowable growth."
                        if cost_pass
                        else f"Cost grew by {cost_increase_pct*100:.1f}% (exceeds {cls.COST_INCREASE_THRESHOLD*100}% limit).",
                    )
                )
                if not cost_pass:
                    has_regressed = True

        summary = "Regression checks PASSED." if not has_regressed else "Regression detected! Quality gates violated."
        return RegressionReport(
            has_regressed=has_regressed,
            checks=checks,
            summary=summary,
        )
