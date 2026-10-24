# Extension guide

For engineers. How to onboard a new BFSI project and how to extend the framework itself. The rule that keeps the
framework reusable: **`evalkit/` never imports `projects/`**. Project-specific behaviour arrives through
`project.yaml` references (`module:attribute`), configuration files and, if needed, an adapter.

Before changing anything: tests first, then code (`uv run --frozen evalkit test`, `uv run --frozen ruff check .`);
configuration is strict, so a new key goes into `evalkit/config/loader.py` and `docs/config_reference.md`.

---

## 1. Onboard a new project

The worked example is `projects/demo_second/` (WP11, a two-tool account-statement bot), and `projects/_template/` is
filled from that experience; both are still empty on 24 Oct 2026, so use `projects/kyc_onboarding/` as the model.

1. **Intake.** Fill the *Template* tab of `docs/requirements/Agent_Requirement_KYC_v0.3.xlsx`: agents, tools and
   their classes, state slices, guardrails, decision rules, risk tier, data, regulatory anchors.
2. **Folder.** Copy `projects/_template/` to `projects/<name>/`.
3. **Tool specs.** One JSON file per tool in `tools/specs/`: `name`, `description`, `x-agent` (the only agent allowed
   to call it), `x-tool-class` (`read` / `interaction` / `write` / `irreversible`), `x-fault-modes`, `input_schema`
   with `additionalProperties: false`, `output_schema`.
4. **agents.yaml.** Each agent's role (`orchestrator` / `specialist`), state slice, output contract
   (`module:PydanticModel` with `extra="forbid"`), where its output appears (`agent_result` or `decision`) and its
   prompt file; plus `protected_attributes` and `scorer_tools` for fairness checks. No pass/fail rules here.
5. **Runner and adapter.** If the system is LangGraph, write a runner that emits the run-event protocol
   (`evalkit/adapters/base.py`) and reuse `LangGraphAdapter`. Otherwise write an adapter (§2).
6. **project.yaml.** Adapter, entrypoint, runner, case source, end-state SQL, tools folder, policies, gates, dataset
   folders, optional catalogue and lint lookups (`docs/config_reference.md`).
7. **Oracles (human-owned).** The QE Lead writes the policy YAML (rules with IDs), `pii_masking.yaml`, the S1
   expectations in the case files and, if the release gates differ, a gates file. Never generate these with the same
   assistant that built the system.
8. **Cases.** One YAML per case (`datasets/<pattern>/<case_id>.yaml`), or import a workbook with `evalkit cases`.
   Then `evalkit lint-cases`, `evalkit coverage`, a dry run, and `evalkit gate --project <name>`.

**Done when** `uv run --frozen evalkit gate --project <name>` runs and `git diff --stat evalkit/` is empty.

## 2. Write an adapter (a new agent framework)

An adapter converts one run into a `Trajectory`; it is the only framework-aware code.

```python
from evalkit.adapters.base import AgentAdapter
from evalkit.schema import RunMeta, Step, ToolCall, Trajectory


class MyFrameworkAdapter(AgentAdapter):
    name = "my_framework"

    def run(self, case, trial, run_id, db_path, client=None) -> Trajectory:
        # 1. start the system with the case's inputs against the per-trial database copy db_path
        # 2. map every model call, tool call, hand-off, interrupt, message and final output into Steps, in order
        # 3. read the end state with self.project.end_state_query on db_path
        # 4. never raise for an agent failure: return a Trajectory with error=... so it is graded, not lost
        ...
```

Rules the evaluators rely on:

- Every `ToolCall` names the `agent` that issued it, and `attempt` counts calls per (tool, identical arguments).
- `fault_injected` is set only by the harness, never from agent output.
- Agent outputs appear as `agent_result` steps (`data.contract`) or `decision` steps for the orchestrator.
- Run inputs (IDs, form, documents) go in a `note` step with content `run_start` and `data.inputs`, so TU-4 can treat
  them as grounding sources.
- The approval step's token appears in the `interrupt` step (`data.token`) so A1 can check its provenance.

Test it with a parity test: re-running recorded runs must reproduce them exactly
(`tests/unit/test_adapter_parity.py` is the model).

## 3. Add a metric or evaluator

1. **Test first.** In `tests/unit/evaluators/`, one test that the check passes on a good trajectory and one that it
   fails on a bad one. Bad trajectories are made from the recordings with the mutation helpers in
   `tests/unit/evaluators/conftest.py` (`drop_tool`, `edit_call`, `add_call`, `set_output`, `with_reply`,
   `with_end_state`, `as_case`).
2. **Implement** an `Evaluator` (one trajectory) or `GroupEvaluator` (several trials or a twin pair) in the right
   family folder:

   ```python
   class MyEvaluator(Evaluator):
       metric = "TU-8"
       severity = "S2"

       def evaluate(self, traj, ctx):
           if not ctx.case.something:
               return [self.skip("case states no …")]  # never pass on missing evidence
           ok, step = ...
           return [self.result("pass" if ok else "fail", "what was checked", step=step)]
   ```

   Read only the `Trajectory` and `EvalContext` — never a framework object or a project module.
3. **Register** it: add the ID to `METRICS` and the class to `TRIAL_EVALUATORS`, `GROUP_EVALUATORS` or
   `AGENT_EVALUATORS` in `evalkit/config/registry.py`.
4. **Gate it (optional, human decision).** A threshold in `configs/gates.yaml` is the QE Lead's and the approver's
   call; an ungated metric is reported only.
5. Document it in `docs/methodology/metrics_catalogue.md`.

Most new KYC-style rules need **no code**: write them as policy rules (`required`, `precedence`, `forbidden`,
`implies`, `allow_list`, `approval_token`, `slice_isolation`, `limit`) — see `docs/config_reference.md › Policy files`.

## 4. Add a judge rubric

1. Define a `Rubric(id, name, question, anchors={3: …, 0: …}, views=(…))` next to the others in
   `evalkit/evaluators/judges/` and add it to `RUBRICS`. Views: `task`, `steps`, `plan`, `replies`, `end_state`.
2. Add the metric to `configs/judges.yaml › metrics` and **bump `rubric_version`** so cached scores are not reused.
3. Tests with a fake client only (`tests/unit/evaluators/test_judges.py`); no live call in tests.
4. The rubric stays advisory (S3) until 30 traces labelled by each tester give κ ≥ 0.6 and ≥ 85% agreement with
   their consensus (`evalkit calibrate`).

## 5. Add a fault type

1. Add the behaviour to `Behaviour` in `evalkit/harness/fault_hook.py` and implement it there; it must stamp
   `fault_injected` and stay deterministic (slow responses use the virtual clock, never a real sleep).
2. Test it in `tests/unit/test_fault_hook.py` (no project involved).
3. In the project, add a fault profile that uses it (KYC: `data/fixtures/kyc_fixtures.py`, then `evalkit data`) and a
   case that names the profile in `fixtures`.

## 6. Add a PII recogniser

1. Add `{entity, description, pattern, checksum?}` to `configs/pii_recognizers.yaml`. `checksum: verhoeff` or `luhn`
   drops look-alikes.
2. Add labelled synthetic examples (positives, masked forms and look-alikes) to `tests/fixtures/pii_labelled.jsonl`;
   recall and precision must stay ≥ 95%.
3. Ask the QE Lead to add a masking rule for the entity to the project's `pii_masking.yaml` (which scopes it may not
   appear in). Without a rule the entity is detected but never fails a check.

## 7. Add a project-specific check without touching evalkit

Prefer, in order: a policy rule (most cases) → a case-level expectation (`expected.agent_outputs`, `expected.arguments`)
→ a guardrail rule with `agent:` and `metric: AG-5`. Only a genuinely new kind of measurement needs a new evaluator, and
that evaluator must work for any project.
