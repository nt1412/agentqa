"use client";

import { useEffect, useState } from "react";
import { useApp } from "@/app/providers";
import { api } from "@/lib/api";
import type { Build, Execution, Milestone, Plan } from "@/lib/types";
import {
  Button,
  Cell,
  EmptyState,
  Field,
  Grid,
  Input,
  Panel,
  Row,
  Spinner,
  Stat,
  StatusBadge,
  Table,
  Tag,
} from "@/components/ui";

export default function PlansPage() {
  const { currentProject } = useApp();

  const [plans, setPlans] = useState<Plan[]>([]);
  const [loadingPlans, setLoadingPlans] = useState(true);
  const [selectedPlan, setSelectedPlan] = useState<Plan | null>(null);

  // right-pane data
  const [builds, setBuilds] = useState<Build[]>([]);
  const [milestones, setMilestones] = useState<Milestone[]>([]);
  const [executions, setExecutions] = useState<Execution[]>([]);
  const [loadingRight, setLoadingRight] = useState(false);

  // new plan form
  const [newName, setNewName] = useState("");
  const [creating, setCreating] = useState(false);

  /* -------- fetch plan list -------- */
  useEffect(() => {
    if (!currentProject) return;
    setLoadingPlans(true);
    setSelectedPlan(null);
    api.plans(currentProject.id).then((ps) => {
      setPlans(ps);
      setLoadingPlans(false);
    }).catch(() => setLoadingPlans(false));
  }, [currentProject]);

  /* -------- fetch right-pane data when plan selected -------- */
  useEffect(() => {
    if (!selectedPlan) return;
    setLoadingRight(true);
    setExecutions([]);
    Promise.all([
      api.builds(selectedPlan.id).catch(() => [] as Build[]),
      api.milestones(selectedPlan.id).catch(() => [] as Milestone[]),
      api.planExecutions(selectedPlan.id).catch(() => [] as Execution[]),
    ]).then(([b, m, e]) => {
      setBuilds(b);
      setMilestones(m);
      setExecutions(e);
      setLoadingRight(false);
    });
  }, [selectedPlan]);

  /* -------- create plan -------- */
  async function handleCreatePlan() {
    if (!currentProject || !newName.trim()) return;
    setCreating(true);
    try {
      await api.createPlan(currentProject.id, newName.trim());
      setNewName("");
      const ps = await api.plans(currentProject.id);
      setPlans(ps);
    } finally {
      setCreating(false);
    }
  }

  /* -------- guards -------- */
  if (!currentProject) return <EmptyState title="no project selected" hint="create one in Admin" />;
  if (loadingPlans) return <Spinner label="loading plans" />;

  /* -------- derived stats -------- */
  const totalExec = executions.length;
  const passCount = executions.filter((e) => e.status === "pass").length;
  const failCount = executions.filter((e) => e.status === "fail").length;

  return (
    <div className="space-y-6">
      {/* page header */}
      <div>
        <h1 className="mono text-lg font-semibold tracking-wide">TEST PLAN MANAGER</h1>
        <p className="label mt-0.5">{currentProject.name} · {currentProject.prefix}</p>
      </div>

      <div className="grid grid-cols-[280px_1fr] gap-6">
        {/* ---- LEFT: plan list + new plan form ---- */}
        <div className="space-y-4">
          <Panel title="plans">
            {plans.length === 0 ? (
              <EmptyState title="no plans yet" />
            ) : (
              <div className="space-y-1">
                {plans.map((p) => (
                  <button
                    key={p.id}
                    onClick={() => setSelectedPlan(p)}
                    className={`w-full border px-3 py-2.5 text-left transition-colors ${
                      selectedPlan?.id === p.id
                        ? "border-[var(--color-accent)] bg-[var(--color-bg-elev-2)]"
                        : "border-[var(--color-border)] hover:border-[var(--color-border-bright)] bg-transparent"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="mono text-sm text-[var(--color-text)]">{p.name}</span>
                      <span className="label">{p.is_open ? "open" : "closed"}</span>
                    </div>
                    <div className="mono mt-0.5 text-[0.6875rem] text-[var(--color-text-faint)]">
                      #{p.id} · {p.active ? "active" : "inactive"}
                    </div>
                  </button>
                ))}
              </div>
            )}
          </Panel>

          {/* new plan form */}
          <Panel title="new plan">
            <div className="space-y-3">
              <Field label="plan name">
                <Input
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleCreatePlan()}
                  placeholder="e.g. sprint-42"
                />
              </Field>
              <Button
                onClick={handleCreatePlan}
                disabled={creating || !newName.trim()}
                className="w-full"
              >
                {creating ? "creating…" : "create plan"}
              </Button>
            </div>
          </Panel>
        </div>

        {/* ---- RIGHT: selected plan detail ---- */}
        {selectedPlan ? (
          <div className="space-y-4">
            {loadingRight ? (
              <Spinner label="loading plan data" />
            ) : (
              <div className="space-y-4"><Grid cols={3}>
                  <Stat label="executions" value={totalExec} />
                  <Stat label="passing" value={passCount} color="var(--color-pass)" />
                  <Stat label="failing" value={failCount} color="var(--color-fail)" />
                </Grid>
                {/* builds */}
                <Panel title="builds" pad={false}>
                  {builds.length === 0 ? (
                    <div className="p-4">
                      <EmptyState title="no builds" />
                    </div>
                  ) : (
                    <Table head={["name", "tag", "branch", "commit", "status"]}>
                      {builds.map((b) => (
                        <Row key={b.id}>
                          <Cell mono>{b.name}</Cell>
                          <Cell>
                            {b.tag ? <Tag>{b.tag}</Tag> : <span className="text-[var(--color-text-faint)]">—</span>}
                          </Cell>
                          <Cell mono className="text-[var(--color-text-dim)]">
                            {b.branch ?? "—"}
                          </Cell>
                          <Cell mono className="text-[var(--color-text-faint)] text-[0.75rem]">
                            {b.commit_id ? b.commit_id.slice(0, 10) : "—"}
                          </Cell>
                          <Cell>
                            <span
                              className="label"
                              style={{ color: b.active ? "var(--color-pass)" : "var(--color-text-faint)" }}
                            >
                              {b.active ? "active" : "inactive"}
                            </span>
                          </Cell>
                        </Row>
                      ))}
                    </Table>
                  )}
                </Panel>

                {/* milestones */}
                <Panel title="milestones" pad={false}>
                  {milestones.length === 0 ? (
                    <div className="p-4">
                      <EmptyState title="no milestones" />
                    </div>
                  ) : (
                    <Table head={["name", "target date"]}>
                      {milestones.map((m) => (
                        <Row key={m.id}>
                          <Cell>{m.name}</Cell>
                          <Cell mono className="text-[var(--color-text-dim)]">
                            {m.target_date ?? "—"}
                          </Cell>
                        </Row>
                      ))}
                    </Table>
                  )}
                </Panel>

                {/* executions */}
                <Panel title="executions" pad={false}>
                  {executions.length === 0 ? (
                    <div className="p-4">
                      <EmptyState title="no executions" />
                    </div>
                  ) : (
                    <Table head={["id", "status", "version", "build", "created"]}>
                      {executions.map((e) => (
                        <Row key={e.id}>
                          <Cell mono className="text-[var(--color-text-faint)]">
                            #{e.id}
                          </Cell>
                          <Cell>
                            <StatusBadge status={e.status} />
                          </Cell>
                          <Cell mono>v{e.version_id}</Cell>
                          <Cell mono>{e.build_id ? `b${e.build_id}` : "—"}</Cell>
                          <Cell mono className="text-[var(--color-text-faint)]">
                            {new Date(e.created_at).toLocaleString()}
                          </Cell>
                        </Row>
                      ))}
                    </Table>
                  )}
                </Panel>
              </div>
            )}
          </div>
        ) : (
          <div className="flex items-center justify-center">
            <EmptyState title="select a plan" hint="choose a plan from the left to view details" />
          </div>
        )}
      </div>
    </div>
  );
}
