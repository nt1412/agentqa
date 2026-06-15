"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { BuildDiff, DiffEntry } from "@/lib/types";
import { Cell, EmptyState, Panel, Row, Spinner, StatusBadge, Table } from "@/components/ui";

// Ordered most-actionable first: regressions scream, then fixes, then the rest.
const SECTIONS: { key: string; label: string; color: string; glyph: string }[] = [
  { key: "regression", label: "newly failing", color: "var(--color-fail)", glyph: "▲" },
  { key: "fixed", label: "fixed", color: "var(--color-pass)", glyph: "▼" },
  { key: "still_failing", label: "still failing", color: "var(--color-blocked)", glyph: "■" },
  { key: "new_test", label: "new tests", color: "var(--color-progress)", glyph: "＋" },
  { key: "removed", label: "removed", color: "var(--color-text-faint)", glyph: "－" },
  { key: "still_passing", label: "still passing", color: "var(--color-notrun)", glyph: "·" },
];

function Section({
  label,
  color,
  glyph,
  entries,
  onPick,
}: {
  label: string;
  color: string;
  glyph: string;
  entries: DiffEntry[];
  onPick: (caseId: number) => void;
}) {
  if (entries.length === 0) return null;
  return (
    <Panel
      title={`${glyph} ${label} · ${entries.length}`}
      pad={false}
      className="!border-l-2"
    >
      <div style={{ boxShadow: `inset 2px 0 0 ${color}` }}>
        <Table head={["id", "case", "baseline", "this build"]}>
          {entries.map((e) => (
            <Row key={e.case_id} onClick={() => onPick(e.case_id)}>
              <Cell mono className="text-[var(--color-text-faint)]">
                {e.external_id}
              </Cell>
              <Cell>{e.name}</Cell>
              <Cell>{e.baseline_status ? <StatusBadge status={e.baseline_status} /> : <span className="mono text-[0.75rem] text-[var(--color-text-faint)]">—</span>}</Cell>
              <Cell>{e.build_status ? <StatusBadge status={e.build_status} /> : <span className="mono text-[0.75rem] text-[var(--color-text-faint)]">—</span>}</Cell>
            </Row>
          ))}
        </Table>
      </div>
    </Panel>
  );
}

export default function ComparePage() {
  const params = useParams();
  const router = useRouter();
  const buildId = Number(params.id);
  const [diff, setDiff] = useState<BuildDiff | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api
      .buildCompare(buildId, "baseline")
      .then(setDiff)
      .finally(() => setLoading(false));
  }, [buildId]);

  if (loading) return <Spinner label="computing diff" />;
  if (!diff) return <EmptyState title="build not found" />;

  const total = Object.values(diff.classes).reduce((n, v) => n + v.length, 0);
  const regressions = diff.classes.regression?.length ?? 0;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="mono text-lg font-semibold tracking-wide">build diff</h1>
        <p className="label mt-0.5">
          build #{buildId} vs{" "}
          {diff.baseline_build_id ? (
            <button
              className="text-[var(--color-accent)] hover:underline"
              onClick={() => router.push(`/builds/${diff.baseline_build_id}`)}
            >
              baseline #{diff.baseline_build_id}
            </button>
          ) : (
            <span className="text-[var(--color-text-faint)]">no baseline — all results are new</span>
          )}
        </p>
      </div>

      <div
        className="border px-4 py-3"
        style={{
          borderColor: regressions ? "var(--color-fail)" : "var(--color-pass)",
          background: regressions
            ? "color-mix(in srgb, var(--color-fail) 8%, transparent)"
            : "color-mix(in srgb, var(--color-pass) 8%, transparent)",
        }}
      >
        <span className="mono text-sm" style={{ color: regressions ? "var(--color-fail)" : "var(--color-pass)" }}>
          {regressions ? `▲ ${regressions} regression${regressions > 1 ? "s" : ""}` : "✓ no regressions"}
        </span>
        <span className="label ml-3 !text-[var(--color-text-faint)]">{total} cases compared</span>
      </div>

      {SECTIONS.map((s) => (
        <Section
          key={s.key}
          label={s.label}
          color={s.color}
          glyph={s.glyph}
          entries={diff.classes[s.key] ?? []}
          onPick={(caseId) => router.push(`/cases/${caseId}`)}
        />
      ))}
    </div>
  );
}
