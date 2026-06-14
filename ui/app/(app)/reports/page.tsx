"use client";

import { useEffect, useState } from "react";
import { useApp } from "@/app/providers";
import { api } from "@/lib/api";
import type { CoverageGap, Execution, TraceabilityRow } from "@/lib/types";
import {
  Cell,
  EmptyState,
  Grid,
  Panel,
  Row,
  Spinner,
  Stat,
  StatusBadge,
  Table,
  statusColor,
} from "@/components/ui";

interface Tally {
  pass: number;
  fail: number;
  blocked: number;
  not_run: number;
  other: number;
  total: number;
}

const STATUS_SEGMENTS: { key: keyof Omit<Tally, "other" | "total">; label: string }[] = [
  { key: "pass", label: "pass" },
  { key: "fail", label: "fail" },
  { key: "blocked", label: "blocked" },
  { key: "not_run", label: "not_run" },
];

export default function Reports() {
  const { currentProject } = useApp();
  const [allExecs, setAllExecs] = useState<Execution[]>([]);
  const [tally, setTally] = useState<Tally>({ pass: 0, fail: 0, blocked: 0, not_run: 0, other: 0, total: 0 });
  const [gaps, setGaps] = useState<CoverageGap[]>([]);
  const [traceability, setTraceability] = useState<TraceabilityRow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!currentProject) return;
    setLoading(true);
    (async () => {
      const [plans, gapsData, traceData] = await Promise.all([
        api.plans(currentProject.id),
        api.coverageGaps(currentProject.id).catch(() => [] as CoverageGap[]),
        api.traceability(currentProject.id).catch(() => [] as TraceabilityRow[]),
      ]);

      const execLists = await Promise.all(
        plans.map((p) => api.planExecutions(p.id).catch(() => [] as Execution[])),
      );
      const all = execLists.flat();

      const t: Tally = { pass: 0, fail: 0, blocked: 0, not_run: 0, other: 0, total: all.length };
      for (const e of all) {
        if (e.status === "pass") t.pass++;
        else if (e.status === "fail") t.fail++;
        else if (e.status === "blocked") t.blocked++;
        else if (e.status === "not_run") t.not_run++;
        else t.other++;
      }

      setTally(t);
      setAllExecs(all);
      setGaps(gapsData);
      setTraceability(traceData);
      setLoading(false);
    })();
  }, [currentProject]);

  if (!currentProject) return <EmptyState title="no project selected" hint="create one in Admin" />;
  if (loading) return <Spinner label="loading reports" />;

  const passRate = tally.total ? Math.round((tally.pass / tally.total) * 100) : 0;

  const failures = [...allExecs]
    .filter((e) => e.status === "fail")
    .sort((a, b) => (a.created_at < b.created_at ? 1 : -1));

  const coveredCount = traceability.length - gaps.length;
  const coverageTotal = traceability.length;
  const coveragePct = coverageTotal ? Math.round((coveredCount / coverageTotal) * 100) : 0;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="mono text-lg font-semibold tracking-wide">{currentProject.name}</h1>
        <p className="label mt-0.5">{currentProject.prefix} · aggregate reports</p>
      </div>

      <Grid cols={4}>
        <Stat label="total executions" value={tally.total} />
        <Stat label="pass rate" value={`${passRate}%`} color="var(--color-pass)" />
        <Stat label="failures" value={tally.fail} color="var(--color-fail)" />
        <Stat label="blocked" value={tally.blocked} color="var(--color-blocked)" />
      </Grid>

      {/* status distribution */}
      <Panel title="status distribution">
        {tally.total === 0 ? (
          <EmptyState title="no executions recorded" />
        ) : (
          <div className="space-y-3">
            {/* composite bar */}
            <div className="flex h-[6px] w-full overflow-hidden">
              {STATUS_SEGMENTS.map(({ key, label }) => {
                const count = tally[key as keyof Tally] as number;
                const pct = tally.total ? (count / tally.total) * 100 : 0;
                if (pct === 0) return null;
                return (
                  <div
                    key={key}
                    title={`${label}: ${count}`}
                    style={{
                      width: `${pct}%`,
                      background: statusColor(label),
                    }}
                  />
                );
              })}
              {/* other bucket */}
              {tally.other > 0 && (
                <div
                  title={`other: ${tally.other}`}
                  style={{
                    width: `${(tally.other / tally.total) * 100}%`,
                    background: "var(--color-text-faint)",
                  }}
                />
              )}
            </div>

            {/* per-status rows */}
            <div className="space-y-2 pt-1">
              {STATUS_SEGMENTS.map(({ key, label }) => {
                const count = tally[key as keyof Tally] as number;
                const pct = tally.total ? (count / tally.total) * 100 : 0;
                return (
                  <div key={key} className="flex items-center gap-3">
                    {/* label */}
                    <span
                      className="mono w-20 shrink-0 text-[0.6875rem] uppercase tracking-wider"
                      style={{ color: statusColor(label) }}
                    >
                      {label.replace("_", " ")}
                    </span>
                    {/* thin track */}
                    <div
                      className="relative flex-1 overflow-hidden"
                      style={{ height: "3px", background: "var(--color-border)" }}
                    >
                      <div
                        style={{
                          position: "absolute",
                          left: 0,
                          top: 0,
                          height: "100%",
                          width: `${pct}%`,
                          background: statusColor(label),
                        }}
                      />
                    </div>
                    {/* mono pct */}
                    <span
                      className="mono w-10 shrink-0 text-right text-[0.6875rem]"
                      style={{ color: "var(--color-text-faint)" }}
                    >
                      {pct.toFixed(1)}%
                    </span>
                    {/* count */}
                    <span
                      className="mono w-8 shrink-0 text-right text-[0.6875rem]"
                      style={{ color: "var(--color-text-dim)" }}
                    >
                      {count}
                    </span>
                  </div>
                );
              })}
              {tally.other > 0 && (
                <div className="flex items-center gap-3">
                  <span
                    className="mono w-20 shrink-0 text-[0.6875rem] uppercase tracking-wider"
                    style={{ color: "var(--color-text-faint)" }}
                  >
                    other
                  </span>
                  <div
                    className="relative flex-1 overflow-hidden"
                    style={{ height: "3px", background: "var(--color-border)" }}
                  >
                    <div
                      style={{
                        position: "absolute",
                        left: 0,
                        top: 0,
                        height: "100%",
                        width: `${(tally.other / tally.total) * 100}%`,
                        background: "var(--color-text-faint)",
                      }}
                    />
                  </div>
                  <span
                    className="mono w-10 shrink-0 text-right text-[0.6875rem]"
                    style={{ color: "var(--color-text-faint)" }}
                  >
                    {((tally.other / tally.total) * 100).toFixed(1)}%
                  </span>
                  <span
                    className="mono w-8 shrink-0 text-right text-[0.6875rem]"
                    style={{ color: "var(--color-text-dim)" }}
                  >
                    {tally.other}
                  </span>
                </div>
              )}
            </div>
          </div>
        )}
      </Panel>

      {/* failure analysis */}
      <Panel title="failure analysis" pad={false}>
        {failures.length === 0 ? (
          <div className="p-4">
            <EmptyState title="no failures recorded" />
          </div>
        ) : (
          <Table head={["exec id", "version", "build", "created"]}>
            {failures.map((e) => (
              <Row key={e.id}>
                <Cell mono>
                  <StatusBadge status={e.status} />
                  <span className="ml-2 text-[var(--color-text-faint)]">#{e.id}</span>
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

      {/* coverage */}
      <Panel title="coverage">
        {coverageTotal === 0 ? (
          <EmptyState title="no traceability data" hint="link requirements to test cases to compute coverage" />
        ) : (
          <div className="space-y-4">
            <div className="flex items-end gap-6">
              <div>
                <div className="label">covered / total</div>
                <div className="mono mt-1 text-2xl font-semibold" style={{ color: "var(--color-pass)" }}>
                  {coveredCount}
                  <span className="text-base font-normal text-[var(--color-text-faint)]">/{coverageTotal}</span>
                </div>
              </div>
              <div>
                <div className="label">gaps</div>
                <div className="mono mt-1 text-2xl font-semibold" style={{ color: gaps.length > 0 ? "var(--color-fail)" : "var(--color-pass)" }}>
                  {gaps.length}
                </div>
              </div>
              <div className="flex-1" />
              <div
                className="mono text-2xl font-semibold"
                style={{ color: coveragePct >= 80 ? "var(--color-pass)" : coveragePct >= 50 ? "var(--color-blocked)" : "var(--color-fail)" }}
              >
                {coveragePct}%
              </div>
            </div>

            {/* coverage bar */}
            <div>
              <div
                className="relative w-full overflow-hidden"
                style={{ height: "4px", background: "var(--color-border)" }}
              >
                <div
                  style={{
                    position: "absolute",
                    left: 0,
                    top: 0,
                    height: "100%",
                    width: `${coveragePct}%`,
                    background: coveragePct >= 80
                      ? "var(--color-pass)"
                      : coveragePct >= 50
                        ? "var(--color-blocked)"
                        : "var(--color-fail)",
                    transition: "width 0.4s ease",
                  }}
                />
              </div>
              <div className="mono mt-1 flex justify-between text-[0.625rem] text-[var(--color-text-faint)]">
                <span>0%</span>
                <span>100%</span>
              </div>
            </div>

            {/* gap list */}
            {gaps.length > 0 && (
              <div className="mt-2 space-y-1.5">
                <div className="label">uncovered requirements</div>
                <div className="space-y-1">
                  {gaps.map((g) => (
                    <div
                      key={g.requirement_id}
                      className="flex items-center gap-3 border border-[var(--color-border)] px-3 py-2"
                    >
                      <span className="mono text-[0.6875rem] text-[var(--color-fail)]">{g.req_doc_id}</span>
                      <span className="mono text-[0.8125rem] text-[var(--color-text-dim)]">{g.name}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </Panel>
    </div>
  );
}
