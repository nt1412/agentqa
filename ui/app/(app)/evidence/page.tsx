"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useApp } from "@/app/providers";
import { api } from "@/lib/api";
import type { Suite, TestCase } from "@/lib/types";
import { Cell, EmptyState, Panel, Row, Spinner, StatusBadge, Table } from "@/components/ui";

export default function EvidenceIndex() {
  const { currentProject } = useApp();
  const [suites, setSuites] = useState<Suite[]>([]);
  const [selected, setSelected] = useState<Suite | null>(null);
  const [cases, setCases] = useState<TestCase[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingCases, setLoadingCases] = useState(false);

  useEffect(() => {
    if (!currentProject) return;
    setLoading(true);
    setSelected(null);
    setCases([]);
    (async () => {
      setSuites(await api.suites(currentProject.id));
      setLoading(false);
    })();
  }, [currentProject]);

  useEffect(() => {
    if (!selected) return;
    setLoadingCases(true);
    (async () => {
      setCases(await api.suiteCases(selected.id));
      setLoadingCases(false);
    })();
  }, [selected]);

  if (!currentProject) return <EmptyState title="no project selected" />;
  if (loading) return <Spinner label="loading evidence index" />;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="mono text-lg font-semibold tracking-wide">evidence</h1>
        <p className="label mt-0.5">{currentProject.prefix} · select a case to inspect its evidence</p>
      </div>

      <div className="grid grid-cols-[300px_1fr] gap-6">
        <Panel title="suites" pad={false}>
          {suites.length === 0 ? (
            <div className="p-4">
              <EmptyState title="no suites" />
            </div>
          ) : (
            <div>
              {suites.map((s) => (
                <button
                  key={s.id}
                  onClick={() => setSelected(s)}
                  className={`block w-full border-b border-[var(--color-border)] px-4 py-2.5 text-left text-sm transition-colors ${
                    selected?.id === s.id
                      ? "bg-[var(--color-bg-elev-2)] text-[var(--color-accent)]"
                      : "text-[var(--color-text-dim)] hover:bg-[var(--color-bg-elev-2)] hover:text-[var(--color-text)]"
                  }`}
                >
                  <span className="mono">{s.name}</span>
                </button>
              ))}
            </div>
          )}
        </Panel>

        <Panel title={selected ? `cases · ${selected.name}` : "cases"} pad={false}>
          {!selected ? (
            <div className="p-4">
              <EmptyState title="pick a suite" hint="then choose a case to open its evidence" />
            </div>
          ) : loadingCases ? (
            <Spinner label="loading cases" />
          ) : cases.length === 0 ? (
            <div className="p-4">
              <EmptyState title="no cases in this suite" />
            </div>
          ) : (
            <Table head={["id", "name", "type", "status", ""]}>
              {cases.map((c) => (
                <Row key={c.id}>
                  <Cell mono>{c.external_id}</Cell>
                  <Cell>{c.name}</Cell>
                  <Cell mono className="text-[var(--color-text-dim)]">
                    {c.current_version?.execution_type ?? "—"}
                  </Cell>
                  <Cell>
                    {c.current_version ? <StatusBadge status={c.current_version.status} /> : "—"}
                  </Cell>
                  <Cell>
                    <Link
                      href={`/evidence/${c.id}`}
                      className="label text-[var(--color-accent)] hover:underline"
                    >
                      evidence →
                    </Link>
                  </Cell>
                </Row>
              ))}
            </Table>
          )}
        </Panel>
      </div>
    </div>
  );
}
