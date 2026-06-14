"use client";

import { useEffect, useState } from "react";
import { useApp } from "@/app/providers";
import { api } from "@/lib/api";
import type { CoverageGap, TraceabilityRow } from "@/lib/types";
import {
  Cell,
  EmptyState,
  Grid,
  Panel,
  Row,
  Spinner,
  Stat,
  Table,
  Tag,
} from "@/components/ui";

export default function TraceabilityPage() {
  const { currentProject } = useApp();

  const [matrix, setMatrix] = useState<TraceabilityRow[]>([]);
  const [gaps, setGaps] = useState<CoverageGap[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!currentProject) return;
    setLoading(true);
    (async () => {
      const [matrixData, gapsData] = await Promise.all([
        api.traceability(currentProject.id).catch(() => [] as TraceabilityRow[]),
        api.coverageGaps(currentProject.id).catch(() => [] as CoverageGap[]),
      ]);
      setMatrix(matrixData);
      setGaps(gapsData);
      setLoading(false);
    })();
  }, [currentProject]);

  if (!currentProject) return <EmptyState title="no project selected" hint="create one in Admin" />;
  if (loading) return <Spinner label="loading traceability" />;

  const coveredCount = matrix.filter((r) => r.covered_case_ids.length > 0).length;
  const gapCount = gaps.length;
  const totalReqs = matrix.length;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="mono text-lg font-semibold tracking-wide">traceability matrix</h1>
        <p className="label mt-0.5">{currentProject.name} · requirement → test case coverage</p>
      </div>

      <Grid cols={4}>
        <Stat label="requirements" value={totalReqs} />
        <Stat
          label="covered"
          value={coveredCount}
          color="var(--color-pass)"
        />
        <Stat
          label="gaps"
          value={gapCount}
          color={gapCount > 0 ? "var(--color-fail)" : "var(--color-pass)"}
        />
        <Stat
          label="coverage"
          value={totalReqs > 0 ? `${Math.round((coveredCount / totalReqs) * 100)}%` : "—"}
          color={
            totalReqs > 0 && coveredCount === totalReqs
              ? "var(--color-pass)"
              : "var(--color-fail)"
          }
        />
      </Grid>

      {/* Main traceability matrix panel */}
      <Panel title="requirement coverage matrix" pad={false}>
        {matrix.length === 0 ? (
          <div className="p-4">
            <EmptyState title="no traceability data" hint="link test cases to requirements via the backend" />
          </div>
        ) : (
          <Table head={["req id", "name", "coverage", "linked cases"]}>
            {matrix.map((row) => {
              const isCovered = row.covered_case_ids.length > 0;
              return (
                <Row key={row.requirement_id}>
                  <Cell mono>{row.req_doc_id}</Cell>
                  <Cell>{row.name}</Cell>
                  <Cell>
                    {isCovered ? (
                      <Tag color="var(--color-pass)">covered</Tag>
                    ) : (
                      <Tag color="var(--color-fail)">gap</Tag>
                    )}
                  </Cell>
                  <Cell mono>
                    {isCovered ? (
                      <span style={{ color: "var(--color-text-dim)" }}>
                        {row.covered_case_ids.join(", ")}
                      </span>
                    ) : (
                      <span style={{ color: "var(--color-text-faint)" }}>—</span>
                    )}
                  </Cell>
                </Row>
              );
            })}
          </Table>
        )}
      </Panel>

      {/* Coverage gaps panel */}
      <Panel title="coverage gaps" pad={false}>
        {gaps.length === 0 ? (
          <div className="p-4">
            <EmptyState title="no gaps detected" hint="all requirements have test coverage" />
          </div>
        ) : (
          <Table head={["req id", "name", "status"]}>
            {gaps.map((gap) => (
              <Row key={gap.requirement_id}>
                <Cell mono>
                  <span style={{ color: "var(--color-fail)" }}>{gap.req_doc_id}</span>
                </Cell>
                <Cell>
                  <span style={{ color: "var(--color-text)" }}>{gap.name}</span>
                </Cell>
                <Cell>
                  <Tag color="var(--color-fail)">uncovered</Tag>
                </Cell>
              </Row>
            ))}
          </Table>
        )}
      </Panel>
    </div>
  );
}
