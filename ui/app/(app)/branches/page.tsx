"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useApp } from "@/app/providers";
import { api } from "@/lib/api";
import type { BranchStatus, KnownRegression } from "@/lib/types";
import { CommitRef, EmptyState, Panel, Spinner, Tag } from "@/components/ui";

function Verdict({ v }: { v: "BLOCKED" | "READY" }) {
  const color = v === "BLOCKED" ? "var(--color-fail)" : "var(--color-pass)";
  return (
    <span
      className="mono inline-flex items-center gap-1.5 border px-2 py-1 text-[0.6875rem] uppercase tracking-wider"
      style={{ color, borderColor: color, background: `color-mix(in srgb, ${color} 8%, transparent)` }}
    >
      <span className="inline-block h-2 w-2 rounded-full" style={{ background: color, boxShadow: `0 0 8px -1px ${color}` }} />
      {v === "BLOCKED" ? "blocked" : "ready"}
    </span>
  );
}

function BranchCard({ b, onCase }: { b: BranchStatus; onCase: (id: number) => void }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border border-[var(--color-border)] bg-[var(--color-bg-elev)]">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between px-4 py-3 text-left hover:bg-[var(--color-bg-elev-2)]"
      >
        <div className="flex items-center gap-3">
          <span className="text-[var(--color-text-faint)]">{open ? "▾" : "▸"}</span>
          <span className="mono text-sm text-[var(--color-text)]">⑂ {b.branch}</span>
          <CommitRef sha={b.head_commit} />
        </div>
        <div className="flex items-center gap-4">
          <span className="mono text-[0.75rem]">
            {b.regressions > 0 && <span style={{ color: "var(--color-fail)" }}>▲ {b.regressions} reg</span>}
            {b.fixed > 0 && <span style={{ color: "var(--color-pass)" }}> ▼ {b.fixed} fixed</span>}
            {b.new_test > 0 && <span style={{ color: "var(--color-progress)" }}> ＋ {b.new_test} new</span>}
            {b.regressions === 0 && b.fixed === 0 && b.new_test === 0 && (
              <span className="text-[var(--color-text-faint)]">no change vs baseline</span>
            )}
          </span>
          <Verdict v={b.verdict} />
        </div>
      </button>
      {open && (
        <div className="border-t border-[var(--color-border)] px-4 py-3">
          <div className="label mb-2">per-plan breakdown</div>
          <div className="space-y-1">
            {b.plans.map((p) => (
              <div key={p.plan_id} className="flex items-center gap-4 text-[0.8125rem]">
                <button
                  className="mono text-[var(--color-text-dim)] hover:text-[var(--color-accent)]"
                  onClick={() => onCase(p.build_id)}
                >
                  plan {p.plan_id} · build #{p.build_id}
                </button>
                <span className="mono text-[0.75rem]">
                  <span style={{ color: p.regressions ? "var(--color-fail)" : "var(--color-text-faint)" }}>
                    {p.regressions} reg
                  </span>
                  {" · "}
                  <span style={{ color: "var(--color-text-faint)" }}>{p.fixed} fixed · {p.new_test} new</span>
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function BranchesPage() {
  const { currentProject } = useApp();
  const router = useRouter();
  const [branches, setBranches] = useState<BranchStatus[]>([]);
  const [known, setKnown] = useState<KnownRegression[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!currentProject) return;
    setLoading(true);
    (async () => {
      try {
        const [b, k] = await Promise.all([
          api.branchStatus(currentProject.id),
          api.knownRegressions(currentProject.id).catch(() => []),
        ]);
        setBranches(b);
        setKnown(k);
      } finally {
        setLoading(false);
      }
    })();
  }, [currentProject]);

  if (!currentProject) return <EmptyState title="no project selected" hint="choose one above" />;
  if (loading) return <Spinner label="evaluating branches" />;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="mono text-lg font-semibold tracking-wide">merge-readiness</h1>
        <p className="label mt-0.5">{currentProject.prefix} · branch vs main, summed across all plans</p>
      </div>

      <Panel title="active branches" pad={false}>
        {branches.length === 0 ? (
          <div className="p-4">
            <EmptyState
              title="no active branches"
              hint="record runs with a branch + base_commit to populate this"
            />
          </div>
        ) : (
          <div className="space-y-px">
            {branches.map((b) => (
              <BranchCard key={b.branch} b={b} onCase={(buildId) => router.push(`/builds/${buildId}/compare`)} />
            ))}
          </div>
        )}
      </Panel>

      <Panel title="known-regression guard · cached fixes">
        {known.length === 0 ? (
          <EmptyState title="no open regressions" hint="nothing to re-investigate" />
        ) : (
          <div className="space-y-3">
            <p className="label !text-[var(--color-text-faint)]">
              each open regression with a known fix-path — read this before re-investigating; it saves an
              expensive model from re-deriving a known answer.
            </p>
            {known.map((k) => (
              <div key={`${k.branch}-${k.case_id}`} className="border border-[var(--color-border)] px-3 py-2.5">
                <div className="flex items-center justify-between">
                  <button
                    className="mono text-sm text-[var(--color-text)] hover:text-[var(--color-accent)]"
                    onClick={() => router.push(`/cases/${k.case_id}`)}
                  >
                    {k.external_id} · {k.name}
                  </button>
                  <span className="label !text-[var(--color-text-faint)]">⑂ {k.branch}</span>
                </div>
                {k.fix_path ? (
                  <div className="mt-2 flex flex-wrap items-center gap-2 text-[0.8125rem]">
                    <Tag color="var(--color-fail)">broke {k.fix_path.broke_commit?.slice(0, 7)}</Tag>
                    <span className="text-[var(--color-text-faint)]">→</span>
                    <Tag color="var(--color-pass)">fixed {k.fix_path.fixed_commit?.slice(0, 7)}</Tag>
                    {k.fix_path.reasoning != null && (
                      <span className="mono text-[0.75rem] text-[var(--color-text-dim)]">
                        {JSON.stringify(k.fix_path.reasoning).slice(0, 120)}
                      </span>
                    )}
                  </div>
                ) : (
                  <div className="mt-1 mono text-[0.75rem] text-[var(--color-text-faint)]">
                    novel regression — no prior fix on record
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
}
