"""Orientation handed to every agent at registration, in-band, so a newly
registered agent can use AgentQA effectively without any out-of-band docs.

Returned by register_agent (MCP tool and REST endpoint). Keep it concise and
actionable; the long-form reference lives in docs/agent-guide.md.
"""

AGENT_ORIENTATION = """\
Welcome to AgentQA — you are now a registered agent. Pass your id (above) as
`agent_id` on every record_test_run so your work is attributable.

RECOMMENDED WORKFLOW
1. Discover before creating: get_suite_tree(project_id), search_test_cases(...).
2. Author: create_test_suite (find-or-create by path), create_test_case /
   bulk_create_test_cases, create_requirement (+ link coverage).
3. Plan: create_test_plan -> add_cases_to_plan(case_ids, urgency 1-3) ->
   add_test_dependency(case_id, depends_on_case_id) for prerequisites.
4. Run off the manifest: get_run_manifest(plan_id, build_id?) returns the
   ordered list with runnable / blocked_by. Run runnable=true top-down; for
   runnable=false, record blocked citing blocked_by (or let cascade do it).
   record_test_run(case_id, plan_id, build_name, status, agent_id=<you>,
   commit_id=<sha>, claims=[...], reasoning={...}, cascade_blocked=true).
5. Self-correct on failure: get_failure_context, search_similar_failures.
6. Audit: list_unverified_claims -> verify_claim -> create_audit_report.

KEY BEHAVIORS
- Build upsert by (plan, build_name); use a per-commit build_name + commit_id
  so "what regressed between builds" is answerable.
- Gating is advisory + cascade: the manifest reports what's blocked; cascade
  auto-blocks downstream on failure. Neither overrides an already-recorded result.
- Per-build gating: get_run_manifest(plan_id, build_id) counts a prerequisite
  only if it passed in that build.
- Idempotent: create_test_suite (by path), add_cases_to_plan,
  add_test_dependency, and coverage links are safe to re-run.

Full reference: docs/agent-guide.md
"""
