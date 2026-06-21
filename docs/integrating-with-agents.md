# Wiring AQA into your coding flow

AQA is reachable three ways over one service layer — **MCP** (for agents), **REST**
(`/api/v1`, docs at `/docs`), and the **`aqa` CLI** (for Bash-tool agents and CI).
For the agentic loop, MCP is the hot path. This guide shows how to connect popular
clients, what to tell your agent, and how to record from CI.

> New here? Read **[agent-guide.md](agent-guide.md)** for the full tool surface and
> the register → plan → run → audit workflow. The orientation is also returned
> in-band by `register_agent` (and readable openly via `get_orientation`).

---

## 1. Connect an agent over MCP

Two transports:

- **streamable-http** — one long-lived server many agents/humans share (recommended
  for a team). Start it:
  ```bash
  AQA_MCP_TRANSPORT=streamable-http AQA_MCP_PORT=8001 python -m app.mcp_server.server
  # → http://localhost:8001/mcp
  ```
- **stdio** — the client spawns AQA per session (no running server needed). Good for
  a single local agent.

### Claude Code
```bash
# http (shared server, must be running)
claude mcp add --transport http aqa http://localhost:8001/mcp

# or stdio (client spawns it)
claude mcp add aqa -- bash -lc 'cd /path/to/aqa && AQA_MCP_TRANSPORT=stdio python -m app.mcp_server.server'
```

### Cursor / Windsurf / Claude Desktop / generic MCP client
Add to the client's MCP config (e.g. `~/.cursor/mcp.json`, `claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "aqa": { "type": "streamable-http", "url": "http://localhost:8001/mcp" }
  }
}
```
stdio variant:
```json
{
  "mcpServers": {
    "aqa": {
      "command": "python",
      "args": ["-m", "app.mcp_server.server"],
      "cwd": "/path/to/aqa",
      "env": { "AQA_MCP_TRANSPORT": "stdio" }
    }
  }
}
```

On connect the agent can call `get_orientation` (open, no auth) to learn the
workflow, then `register_agent` to get its identity.

---

## 2. Make AQA part of the TDD loop (project rules)

Connecting (§1) only makes the tools *available* — it doesn't make the agent *call*
them. The rules file your tool reads **every turn** is what fires the behavior at the
right moments: **Claude Code → `CLAUDE.md`**, **Cursor → `.cursorrules`** (or
`.cursor/rules/*.mdc`), **Codex → `AGENTS.md`**, or a system prompt. Paste this block
and tune to your stack:

```markdown
## AQA loop (required, not optional)

You have an `aqa` MCP server — the team's test-management + verification memory.

- Once per session: `register_agent(login, agent_model)` → follow the returned
  `orientation`; reuse the returned id as `agent_id`. New project? `create_project`.
- **When a requirement is finalized — BEFORE writing code:**
  `create_requirement(spec_id, req_doc_id, name)`. It now shows up in
  `get_coverage_gaps` as unfinished work.
- **TDD:** write the FAILING test first (`create_test_case` under a meaningful
  suite). When it passes, `link_coverage(req_id, [case_id])` to close the gap.
  "Done" means the requirement's coverage gap is closed.
- **After any change:** `record_test_run(case_id, plan_id, build_name, status,
  commit_id, branch, base_commit)`. Record the real status — if a case can't run,
  record `blocked`, never fake `pass`.
- **Before investigating a failure:** call `get_failure_context(case_id)` first —
  it returns this case's recent failures, prior reasoning, and **the last passing
  run's reasoning** (why it was last green, often the fix for a recurrence). For a
  pattern recurring across *other* cases, `search_recurrences(query_text)` does a
  keyword search over prior failure/fix reasoning (pass and fail) — an empty result
  means "no known prior" (a real signal, not an error). `get_known_regressions(project_id,
  branch)` gives a cached cross-case fix-path. Reuse what comes back instead of
  re-deriving (saves an expensive investigation).
- **Claims you can't self-verify:** attach a `claim` to the run; a separate auditor
  confirms/refutes it (see §3). Don't verify your own claims.
- **Encode prerequisites:** `add_test_dependency` so a downstream case is gated on
  its prerequisite (a "pass" downstream of a broken prereq is a lie).
- **Never claim done** while `get_coverage_gaps(project_id)` still lists your
  requirement.
```

The point: *registering the requirement and closing its coverage gap is part of
"done,"* not an afterthought.

### Enforce it (don't rely on the model remembering)

For "**whenever** X, do Y", make the harness enforce it deterministically rather than
trusting the prompt:

- **Claude Code hooks** (`.claude/settings.json`): a `Stop` hook that runs
  `aqa req gaps <project_id>` and blocks completion while gaps remain; a `PostToolUse`
  hook on `Write|Edit` of `tests/**` to nudge `link_coverage`.
- **CI:** record results on every push (see §5) so attribution happens even if an
  agent forgets — `scripts/dogfood.py` imports a JUnit run through the REST front door.
- **Plan templates:** if you generate task plans, bake the touchpoints into each task
  — register requirement → RED → `link_coverage` → GREEN → `record_test_run`.

**Layering:** MCP = capability (§1), rules file = intent (flexible, model-driven),
hooks/CI = enforcement (deterministic, unskippable). Use rules for the loop and a
`Stop`/CI gate for "coverage gaps must be 0."

---

## 3. The doer ≠ checker pattern

Run a second, separate agent as the **auditor** so verification is independent:

```
loop:
  claims = list_unverified_claims(project_id)
  for c in claims:
      verdict = <independently check c.claim_text against the evidence>
      verify_claim(c.id, verdict, reasoning)   # confirmed | refuted | inconclusive
```

Because the auditor registers as its own identity (and, with auth on, the
authenticated identity drives attribution), the checker is provably not the doer.

---

## 4. Record from CI

Your pipeline already runs tests; have it record the results into AQA so history is
attributable across humans and agents. Map each test to a case once, then:

```bash
export AQA_API_URL=http://localhost:8000
export AQA_API_KEY=<an agent key from `aqa agent register`>

aqa run record <case_id> \
  --plan <plan_id> --build "$GIT_SHA" --status "$STATUS" \
  --commit "$GIT_SHA" --cascade
```

`--build` upserts by (plan, name); `--commit` backfills the SHA so "what regressed
between builds" is answerable; `--cascade` auto-blocks downstream cases when a
prerequisite fails. (See `scripts/dogfood.py` for a JUnit-XML → AQA importer — AQA
catalogs its *own* pytest suite into itself this way.)

---

## 5. Auth in shared/production setups

By default the MCP layer is open (fine for a trusted local loop). For a shared
server, enable per-agent auth:

```bash
AQA_MCP_REQUIRE_AUTH=true AQA_MCP_ENROLL_KEY=<join-secret> \
AQA_MCP_TRANSPORT=streamable-http python -m app.mcp_server.server
```

Then agents send `X-API-Key: <their key>` on every call, and **registration**
requires `X-Enroll-Key: <join-secret>` (so open registration can't mint keys).
Revoke an agent with `deactivate_agent` / `aqa agent deactivate <id>`.

**Cold-start over REST/CLI.** Only the MCP `register_agent` is open onboarding by
default. An agent driving the **REST/CLI** (e.g. Cursor/Codex via the `aqa` CLI) can
still mint its own identity by passing the same enrollment secret — `X-Enroll-Key`
header (REST) or `aqa agent register --enroll-key …` / `AQA_ENROLL_KEY` env (CLI). It
fails closed: with no secret configured, REST/CLI registration is refused.

---

## What you get

The longer your agents work against AQA, the more your suite becomes the accumulated
memory of everything that ever went wrong — a reliability ratchet that compounds per
commit, per session, per agent. AQA doesn't run your tests or invent correctness; it
makes the verification you already do durable, attributable, and impossible to fake.
