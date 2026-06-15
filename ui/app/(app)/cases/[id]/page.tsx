"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useApp } from "@/app/providers";
import { api } from "@/lib/api";
import type { CaseHistory, Execution, TestCase } from "@/lib/types";
import {
  Button,
  Cell,
  EmptyState,
  Panel,
  Row,
  Sparkline,
  Spinner,
  StatusBadge,
  Table,
  Tag,
} from "@/components/ui";

export default function CaseEditorPage() {
  const params = useParams();
  const router = useRouter();
  const { currentProject } = useApp();

  const caseId = Number(params.id);

  const [testCase, setTestCase] = useState<TestCase | null>(null);
  const [executions, setExecutions] = useState<Execution[]>([]);
  const [history, setHistory] = useState<CaseHistory | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    if (!caseId || isNaN(caseId)) return;
    setLoading(true);
    setNotFound(false);
    (async () => {
      try {
        const [tc, execs, hist] = await Promise.all([
          api.case(caseId),
          api.caseExecutions(caseId).catch(() => [] as Execution[]),
          api.caseHistory(caseId).catch(() => null),
        ]);
        setTestCase(tc);
        setExecutions(execs);
        setHistory(hist);
      } catch {
        setNotFound(true);
      } finally {
        setLoading(false);
      }
    })();
  }, [caseId]);

  if (loading) return <Spinner label="loading case" />;
  if (notFound || !testCase) return <EmptyState title="case not found" hint={`id ${caseId} does not exist`} />;

  const cv = testCase.current_version;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-3">
            <span className="mono text-[var(--color-text-faint)] text-sm">{testCase.external_id}</span>
            {cv && <StatusBadge status={cv.status} />}
          </div>
          <h1 className="mono text-lg font-semibold tracking-wide mt-1">{testCase.name}</h1>
          <p className="label mt-0.5">
            {currentProject?.prefix && `${currentProject.prefix} · `}case #{testCase.id}
          </p>
        </div>
        <Button variant="ghost" onClick={() => router.push(`/evidence/${caseId}`)}>
          view evidence →
        </Button>
      </div>

      {/* Current version panel */}
      <Panel title="current version">
        {cv == null ? (
          <EmptyState title="no version available" />
        ) : (
          <div className="space-y-4">
            {/* Meta row */}
            <div className="flex items-center gap-4 flex-wrap">
              <div>
                <span className="label block mb-1">status</span>
                <StatusBadge status={cv.status} />
              </div>
              <div>
                <span className="label block mb-1">importance</span>
                <Tag>{cv.importance}</Tag>
              </div>
              <div>
                <span className="label block mb-1">execution type</span>
                <Tag>{cv.execution_type}</Tag>
              </div>
              <div>
                <span className="label block mb-1">version</span>
                <span className="mono text-sm text-[var(--color-text-dim)]">v{cv.version}</span>
              </div>
            </div>

            {/* Summary */}
            {cv.summary && (
              <div>
                <span className="label block mb-1">summary</span>
                <p className="text-sm text-[var(--color-text-dim)] leading-relaxed">{cv.summary}</p>
              </div>
            )}

            {/* Preconditions */}
            {cv.preconditions && (
              <div>
                <span className="label block mb-1">preconditions</span>
                <p className="text-sm text-[var(--color-text-dim)] leading-relaxed">{cv.preconditions}</p>
              </div>
            )}

            {/* Steps table */}
            {cv.steps && cv.steps.length > 0 && (
              <div>
                <span className="label block mb-2">steps</span>
                <Table head={["#", "action", "expected result"]}>
                  {cv.steps.map((step) => (
                    <Row key={step.id}>
                      <Cell mono className="text-[var(--color-text-faint)] w-10">
                        {step.step_number}
                      </Cell>
                      <Cell>{step.action}</Cell>
                      <Cell className="text-[var(--color-text-dim)]">
                        {step.expected_result ?? <span className="text-[var(--color-text-faint)]">—</span>}
                      </Cell>
                    </Row>
                  ))}
                </Table>
              </div>
            )}
          </div>
        )}
      </Panel>

      {/* Run lineage — per-build sparkline + derived broke/fixed path */}
      {history && history.executions.length > 0 && (
        <Panel title="run lineage">
          <div className="space-y-3">
            <div className="flex items-center gap-3">
              <span className="label">across builds</span>
              <Sparkline
                points={history.executions.map((e) => ({
                  status: e.status,
                  title: `${e.build_name} · ${e.commit_id?.slice(0, 7) ?? "no commit"} · ${e.status}`,
                }))}
              />
              <span className="mono text-[0.6875rem] text-[var(--color-text-faint)]">
                oldest → newest
              </span>
            </div>
            {history.transitions.length > 0 && (
              <div className="flex flex-wrap items-center gap-2">
                <span className="label">transitions</span>
                {history.transitions.map((t, i) => (
                  <Tag
                    key={i}
                    color={t.type === "broke" ? "var(--color-fail)" : "var(--color-pass)"}
                  >
                    {t.type} {t.commit_id?.slice(0, 7) ?? ""}
                  </Tag>
                ))}
              </div>
            )}
          </div>
        </Panel>
      )}

      {/* Execution history */}
      <Panel title="execution history" pad={false}>
        {executions.length === 0 ? (
          <div className="p-4">
            <EmptyState title="no executions recorded" />
          </div>
        ) : (
          <Table head={["exec", "status", "build", "when", "evidence"]}>
            {executions.map((e) => (
              <Row key={e.id}>
                <Cell mono className="text-[var(--color-text-faint)]">
                  #{e.id}
                </Cell>
                <Cell>
                  <StatusBadge status={e.status} />
                </Cell>
                <Cell mono>
                  {e.build_id ? `b${e.build_id}` : <span className="text-[var(--color-text-faint)]">—</span>}
                </Cell>
                <Cell mono className="text-[var(--color-text-faint)]">
                  {new Date(e.created_at).toLocaleString()}
                </Cell>
                <Cell>
                  <button
                    onClick={() => router.push(`/evidence/${caseId}`)}
                    className="mono text-[0.6875rem] uppercase tracking-wider text-[var(--color-accent)] hover:underline"
                  >
                    evidence →
                  </button>
                </Cell>
              </Row>
            ))}
          </Table>
        )}
      </Panel>
    </div>
  );
}
