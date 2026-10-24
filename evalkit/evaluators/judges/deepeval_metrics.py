"""Trajectory judges (TR-8): task completion and plan adherence — the DeepEval metrics' aims, run on our own judge.

Feasibility check of DeepEval (WP7 task 1, 23 Oct 2026, deepeval 4.3.1, read from its source, no live call):
  * TaskCompletionMetric, StepEfficiencyMetric and PlanAdherenceMetric set `requires_trace = True` and read the private
    `LLMTestCase._trace_dict`, which DeepEval fills only when the agent runs under its own `@observe` tracing. A
    pre-built trace could only be passed by forging that private attribute in DeepEval's internal trace format — an
    undocumented interface that can change in any release.
  * Their scores are 0–1 and their rubrics are DeepEval's; the SOP's calibration (§3.9) uses anchored 0–3 labels.
  * Their model wrappers would have to pass the current Claude API's rules (no sampling parameters, pinned effort).
Decision: the same two aims are scored by RubricJudge with the SOP's anchors on our canonical Trajectory, so tester
labels and judge scores share one scale. StepEfficiency is not judged: the SOP gives it no anchors, and the
deterministic TR-6 / AG-6 already measure it.
"""

from __future__ import annotations

from evalkit.evaluators.judges.geval_rubric import CUSTOMER_EXPLANATION, Rubric

TASK_COMPLETION = Rubric(
    id="TR-8.task",
    name="Task completion",
    question="Did the run achieve the customer's onboarding goal, with an end state and a final message that agree?",
    anchors={
        3: "Goal fully met; end state and message consistent",
        2: "Goal met with a minor gap (e.g. missing next-step detail)",
        1: "Partially met; key element missing",
        0: "Not met, wrong or unsafe",
    },
    views=("task", "steps", "replies", "end_state"),
)

PLAN_ADHERENCE = Rubric(
    id="TR-8.plan",
    name="Plan adherence",
    question="Did the agents follow the expected plan of controls, with any deviation justified by what the tools returned?",
    anchors={
        3: "Follows the expected plan; deviations justified",
        2: "Minor unnecessary step; plan still sound",
        1: "Material deviation or skipped reasoning",
        0: "No coherent plan; contradictory steps",
    },
    views=("task", "plan", "steps"),
)

RUBRICS: dict[str, Rubric] = {r.id: r for r in (TASK_COMPLETION, PLAN_ADHERENCE, CUSTOMER_EXPLANATION)}
