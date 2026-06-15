"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useApp } from "@/app/providers";
import { api } from "@/lib/api";
import type { ProjectHealth } from "@/lib/types";
import {
  Button,
  Cell,
  CommitRef,
  EmptyState,
  Grid,
  Panel,
  RollupBar,
  Row,
  Spinner,
  Stat,
  Table,
} from "@/components/ui";

// Mini pass-rate bar chart across recent builds — oldest→newest.
function Trend({ points }: { points: { pass_rate: number; name: string }[] }) {
  if (points.length === 0) return <EmptyState title="no builds yet" />;
  return (
    <div className="flex items-end gap-1" style={{ height: 80 }}>
      {points.map((p, i) => (
        <div
          key={i}
          title={`${p.name}: ${p.pass_rate}%`}
          className="flex-1 transition-all"
          style={{
            height: `${Math.max(p.pass_rate, 3)}%`,
            background:
              p.pass_rate >= 90
                ? "var(--color-pass)"
                : p.pass_rate >= 60
                  ? "var(--color-blocked)"
                  : "var(--color-fail)",
            opacity: 0.5 + (0.5 * (i + 1)) / points.length,
          }}
        />
      ))}
    </div>
  );
}

export default function HealthPage() {
  const { currentProject } = useApp();
  const router = useRouter();
  const [health, setHealth] = useState<ProjectHealth | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!currentProject) return;
    setHealth(await api.projectHealth(currentProject.id));
  }, [currentProject]);

  useEffect(() => {
    if (!currentProject) return;
    setLoading(true);
    load().finally(() => setLoading(false));
  }, [currentProject, load]);

  async function toggleQuarantine(caseId: number, value: boolean) {
    await api.setQuarantine(caseId, value);
    await load(); // re-pull so the metric/flaky list reflect it
  }

  if (!currentProject) return <EmptyState title="no project selected" hint="choose one above" />;
  if (loading || !health) return <Spinner label="assessing health" />;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="mono text-lg font-semibold tracking-wide">project health</h1>
        <p className="label mt-0.5">{currentProject.prefix} · situational overview</p>
      </div>

      <Grid cols={4}>
        <Stat
          label="open regressions"
          value={health.open_regressions}
          color={health.open_regressions ? "var(--color-fail)" : "var(--color-pass)"}
        />
        <Stat
          label="re-investigations avoidable"
          value={health.reinvestigations_avoidable}
          color="var(--color-accent)"
          hint="open regressions with a cached fix"
        />
        <Stat label="flaky candidates" value={health.flaky_candidates.length} color="var(--color-blocked)" />
        <Stat label="plans" value={health.plans.length} />
      </Grid>

      <div className="grid grid-cols-[1.4fr_1fr] gap-6">
        <Panel title="pass-rate trend · recent builds">
          <Trend points={health.trend.map((t) => ({ pass_rate: t.pass_rate, name: t.name }))} />
          <p className="label mt-3 !text-[var(--color-text-faint)]">oldest → newest, across all plans</p>
        </Panel>

        <Panel title="plans" pad={false}>
          {health.plans.length === 0 ? (
            <div className="p-4">
              <EmptyState title="no plans" />
            </div>
          ) : (
            <div className="divide-y divide-[var(--color-border)]">
              {health.plans.map((p) => (
                <button
                  key={p.plan_id}
                  onClick={() => p.latest_build && router.push(`/builds/${p.latest_build.id}`)}
                  className="flex w-full items-center justify-between px-4 py-3 text-left hover:bg-[var(--color-bg-elev-2)]"
                >
                  <div>
                    <div className="mono text-sm">{p.name}</div>
                    {p.latest_build ? (
                      <div className="mt-1">
                        <CommitRef
                          sha={p.latest_build.commit_id}
                          branch={p.latest_build.branch}
                          repoUrl={currentProject.options?.repo_url as string | undefined}
                        />
                      </div>
                    ) : (
                      <div className="label mt-1 !text-[var(--color-text-faint)]">no builds</div>
                    )}
                  </div>
                  {p.latest_build && <RollupBar rollup={p.latest_build.rollup} width={120} />}
                </button>
              ))}
            </div>
          )}
        </Panel>
      </div>

      <Panel title={`flaky candidates · ${health.flaky_candidates.length}`} pad={false}>
        {health.flaky_candidates.length === 0 ? (
          <div className="p-4">
            <EmptyState title="no flaky candidates" hint="no cases flip-flopping across builds" />
          </div>
        ) : (
          <Table head={["id", "case", "flips", "status", ""]}>
            {health.flaky_candidates.map((f) => (
              <Row key={f.case_id}>
                <Cell mono className="text-[var(--color-text-faint)]">
                  {f.external_id}
                </Cell>
                <Cell>
                  <button
                    className="text-left hover:text-[var(--color-accent)]"
                    onClick={() => router.push(`/cases/${f.case_id}`)}
                  >
                    {f.name}
                  </button>
                </Cell>
                <Cell mono>
                  <span style={{ color: "var(--color-blocked)" }}>{f.flips}×</span>
                </Cell>
                <Cell>
                  {f.quarantined ? (
                    <span className="mono text-[0.6875rem] uppercase tracking-wider text-[var(--color-notrun)]">
                      quarantined
                    </span>
                  ) : (
                    <span className="mono text-[0.6875rem] uppercase tracking-wider text-[var(--color-text-faint)]">
                      active
                    </span>
                  )}
                </Cell>
                <Cell>
                  <Button
                    variant="ghost"
                    onClick={() => toggleQuarantine(f.case_id, !f.quarantined)}
                  >
                    {f.quarantined ? "un-quarantine" : "quarantine"}
                  </Button>
                </Cell>
              </Row>
            ))}
          </Table>
        )}
      </Panel>
    </div>
  );
}
