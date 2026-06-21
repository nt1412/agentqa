# AQA — working agreement for coding agents (Codex / generic)

AQA is test-management + a verification memory for the agentic loop, and this repo
**dogfoods its own product**. Recording in AQA is part of "done". MCP:
`http://localhost:8001/mcp` · REST: `http://localhost:8000` · the `aqa` CLI. Full
recipes: `docs/integrating-with-agents.md`.

## AQA verification loop (required, not optional)

1. **Requirement finalized** → `create_requirement(spec_id, req_doc_id, name)` BEFORE
   code. It shows in `get_coverage_gaps` until covered.
2. **TDD** → write the **failing** test first; on green, `link_coverage(req_id, [case_id])`.
   "Done" = the gap is closed.
3. **After a change** → `record_test_run(case_id, plan_id, build_name, status,
   commit_id, branch, base_commit)` (`base_commit = git merge-base HEAD main`).
   **On any FAILED run you MUST attach a 1–2 sentence `reasoning` root-cause** —
   it is the only text the failure memory embeds/recalls; no reasoning = invisible.
4. **Before investigating a failure** → `get_failure_context(case_id)` first — it
   returns this case's recent failures, prior reasoning, and **the last passing run's
   reasoning** (why it was last green — often the fix for a recurrence). Also
   `get_known_regressions(project_id, branch)` for a cached cross-case fix-path;
   reuse what's there instead of re-deriving.
5. **Don't claim done** while `get_coverage_gaps(project_id)` lists your requirement.

Onboarding over REST/CLI needs the operator's enrollment secret: set `AQA_ENROLL_KEY`
(sent as `X-Enroll-Key`). Only MCP `register_agent` is open onboarding.
