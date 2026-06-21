# AQA — working agreement for coding agents

AQA is test-management + a verification memory for the agentic loop. This repo
**dogfoods its own product**: requirements, tests, runs, and coverage are tracked in
AQA. Recording in AQA is part of "done", not an afterthought.

AQA is reachable at **MCP** `http://localhost:8001/mcp`, **REST** `http://localhost:8000`,
and the `aqa` CLI. Full recipes: `docs/integrating-with-agents.md`.

## AQA verification loop (required, not optional)

1. **Requirement finalized** → `create_requirement(spec_id, req_doc_id, name)` BEFORE
   writing code. It now shows in `get_coverage_gaps` as unfinished work.
2. **TDD** → write the **failing** test first (red). When it passes (green), call
   `link_coverage(req_id, [case_id])` to close the gap. "Done" = the gap is closed.
3. **After a change** → `record_test_run(case_id, plan_id, build_name, status,
   commit_id, branch, base_commit)`. Pass `branch` and `base_commit`
   (`git merge-base HEAD main`) so a branch's delta vs main resolves precisely.
   **On any FAILED run, you MUST attach a 1–2 sentence `reasoning` root-cause** —
   this is the only text the failure memory embeds and later recalls; a failure
   recorded without reasoning is invisible to retrieval (and to the team).
4. **Before investigating a failure** → `get_known_regressions(project_id, branch)`.
   If a fix-path is cached, reuse it instead of re-deriving (saves expensive tokens).
5. **Don't claim done** while `get_coverage_gaps(project_id)` lists your requirement.

Onboarding: call `register_agent` over MCP once (open). Over REST/CLI it needs the
operator's enrollment secret — set `AQA_ENROLL_KEY` (sent as `X-Enroll-Key`).

## Enforcement (this repo)

`.claude/settings.json` wires two hooks (deterministic, "every time"):
- **Stop** → `scripts/coverage_gate.py` blocks finishing while the AQA project has open
  coverage gaps (fails open if AQA is unreachable).
- **PostToolUse** on `tests/**` → `scripts/link_coverage_nudge.py` reminds you to link
  coverage. CI also records runs via `scripts/dogfood.py` as the can't-skip backstop.
