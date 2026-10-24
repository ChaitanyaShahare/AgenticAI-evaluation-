# E2 — Choose a match mode (M3 · 30 min)

For each scenario choose `strict`, `unordered`, `subset` or `superset` for TR-2, and say in one line why. Remember that
precedence rules (TR-4) already enforce the compliance-critical orders.

1. The identity agent's `ckyc_lookup` and `check_address_proof` may run in either order.
2. A golden approval where the Supervisor may ask the customer one clarifying question before finishing.
3. An injected-document case that must make exactly the same tool calls as its clean twin (order may vary).
4. A case about write tools, where calling `escalate_to_edd` or `create_customer_record` when not in the reference is
   itself a risk.
5. The corporate applicant: route to the corporate stub, then finalise — nothing else, in that order.
6. A tool-fault case where the agent may retry a timed-out call up to twice before moving on.

Answers: `expected_answers.md › E2`.
