"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useApp } from "@/app/providers";
import { api } from "@/lib/api";
import type { CaseStatusMap, Suite, TestCase } from "@/lib/types";
import {
  Button,
  Cell,
  EmptyState,
  Field,
  Input,
  Panel,
  Row,
  Select,
  Sparkline,
  Spinner,
  StatusBadge,
  Table,
  Tag,
} from "@/components/ui";

/* ---------- tree helpers ---------- */

interface TreeNode extends Suite {
  children: TreeNode[];
}

function buildTree(suites: Suite[]): TreeNode[] {
  const map = new Map<number, TreeNode>();
  for (const s of suites) map.set(s.id, { ...s, children: [] });
  const roots: TreeNode[] = [];
  for (const s of suites) {
    const node = map.get(s.id)!;
    if (s.parent_id === null) roots.push(node);
    else map.get(s.parent_id)?.children.push(node);
  }
  const sort = (nodes: TreeNode[]) => {
    nodes.sort((a, b) => a.order - b.order);
    nodes.forEach((n) => sort(n.children));
  };
  sort(roots);
  return roots;
}

function pathTo(suites: Suite[], id: number | null): Suite[] {
  if (id === null) return [];
  const byId = new Map(suites.map((s) => [s.id, s]));
  const chain: Suite[] = [];
  let cur = byId.get(id) ?? null;
  while (cur) {
    chain.unshift(cur);
    cur = cur.parent_id !== null ? byId.get(cur.parent_id) ?? null : null;
  }
  return chain;
}

/* ---------- tree row (expand/collapse) ---------- */

function SuiteRow({
  node,
  depth,
  selectedId,
  expanded,
  onSelect,
  onToggle,
}: {
  node: TreeNode;
  depth: number;
  selectedId: number | null;
  expanded: Set<number>;
  onSelect: (id: number) => void;
  onToggle: (id: number) => void;
}) {
  const isSelected = node.id === selectedId;
  const hasChildren = node.children.length > 0;
  const isOpen = expanded.has(node.id);
  return (
    <>
      <div
        className={`group flex items-center border-b border-[var(--color-border)] transition-colors hover:bg-[var(--color-bg-elev-2)] ${
          isSelected ? "bg-[var(--color-bg-elev-2)]" : ""
        }`}
        style={{ paddingLeft: `${8 + depth * 14}px` }}
      >
        <button
          onClick={() => hasChildren && onToggle(node.id)}
          className={`w-5 shrink-0 text-center text-[var(--color-text-faint)] ${hasChildren ? "" : "opacity-0"}`}
        >
          {isOpen ? "▾" : "▸"}
        </button>
        <button
          onClick={() => onSelect(node.id)}
          className={`flex flex-1 items-center gap-2 py-2 pr-3 text-left mono text-[0.8125rem] ${
            isSelected ? "text-[var(--color-accent)]" : "text-[var(--color-text)]"
          }`}
        >
          <span className="truncate">{node.name}</span>
          {hasChildren && (
            <span className="ml-auto label text-[var(--color-text-faint)]">{node.children.length}</span>
          )}
        </button>
      </div>
      {isOpen &&
        node.children.map((child) => (
          <SuiteRow
            key={child.id}
            node={child}
            depth={depth + 1}
            selectedId={selectedId}
            expanded={expanded}
            onSelect={onSelect}
            onToggle={onToggle}
          />
        ))}
    </>
  );
}

/* ---------- main ---------- */

export default function SuitesPage() {
  const { currentProject } = useApp();
  const router = useRouter();

  const [suites, setSuites] = useState<Suite[]>([]);
  const [caseStatus, setCaseStatus] = useState<CaseStatusMap>({});
  const [loadingSuites, setLoadingSuites] = useState(true);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [expanded, setExpanded] = useState<Set<number>>(new Set());

  const [cases, setCases] = useState<TestCase[]>([]);
  const [loadingCases, setLoadingCases] = useState(false);

  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all");
  const [newSuite, setNewSuite] = useState("");

  const storageKey = currentProject ? `aqa_suites_expanded_${currentProject.id}` : null;

  // load suites + per-case latest-run status; restore expanded state
  useEffect(() => {
    if (!currentProject) return;
    setSelectedId(null);
    setSuites([]);
    setLoadingSuites(true);
    (async () => {
      try {
        const [data, smap] = await Promise.all([
          api.suites(currentProject.id),
          api.caseStatusMap(currentProject.id).catch(() => ({}) as CaseStatusMap),
        ]);
        setSuites(data);
        setCaseStatus(smap);
        if (storageKey) {
          try {
            const saved = JSON.parse(localStorage.getItem(storageKey) ?? "[]");
            setExpanded(new Set(saved));
          } catch {
            setExpanded(new Set());
          }
        }
      } finally {
        setLoadingSuites(false);
      }
    })();
  }, [currentProject, storageKey]);

  useEffect(() => {
    if (selectedId === null) {
      setCases([]);
      return;
    }
    setLoadingCases(true);
    (async () => {
      try {
        setCases(await api.suiteCases(selectedId));
      } finally {
        setLoadingCases(false);
      }
    })();
  }, [selectedId]);

  function toggle(id: number) {
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      if (storageKey) localStorage.setItem(storageKey, JSON.stringify([...next]));
      return next;
    });
  }

  async function createSuite() {
    const name = newSuite.trim();
    if (!name || !currentProject) return;
    await api.createSuite(currentProject.id, name, selectedId ?? undefined);
    setNewSuite("");
    setSuites(await api.suites(currentProject.id));
  }

  const tree = useMemo(() => buildTree(suites), [suites]);
  const crumbs = useMemo(() => pathTo(suites, selectedId), [suites, selectedId]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return cases.filter((c) => {
      if (q && !c.name.toLowerCase().includes(q) && !c.external_id.toLowerCase().includes(q))
        return false;
      if (statusFilter !== "all") {
        const st = caseStatus[String(c.id)]?.latest_status ?? "not_run";
        if (st !== statusFilter) return false;
      }
      if (typeFilter !== "all" && c.current_version?.execution_type !== typeFilter) return false;
      return true;
    });
  }, [cases, search, statusFilter, typeFilter, caseStatus]);

  if (!currentProject) return <EmptyState title="no project selected" hint="choose one above" />;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="mono text-lg font-semibold tracking-wide">test suites</h1>
        <p className="label mt-0.5">{currentProject.prefix} · suite browser</p>
      </div>

      <div className="grid grid-cols-[300px_1fr] items-start gap-6">
        {/* tree */}
        <Panel title="suites" pad={false}>
          {loadingSuites ? (
            <div className="p-4">
              <Spinner label="loading suites" />
            </div>
          ) : tree.length === 0 ? (
            <div className="p-4">
              <EmptyState title="no suites" />
            </div>
          ) : (
            <div className="max-h-[70vh] overflow-y-auto">
              {tree.map((node) => (
                <SuiteRow
                  key={node.id}
                  node={node}
                  depth={0}
                  selectedId={selectedId}
                  expanded={expanded}
                  onSelect={setSelectedId}
                  onToggle={toggle}
                />
              ))}
            </div>
          )}
          <div className="flex items-center gap-2 border-t border-[var(--color-border)] p-3">
            <Input
              value={newSuite}
              onChange={(e) => setNewSuite(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && createSuite()}
              placeholder={selectedId ? "new child suite…" : "new root suite…"}
            />
            <Button variant="ghost" onClick={createSuite} disabled={!newSuite.trim()}>
              add
            </Button>
          </div>
        </Panel>

        {/* cases */}
        <div className="space-y-3">
          {/* breadcrumbs */}
          {crumbs.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5 mono text-[0.8125rem]">
              {crumbs.map((s, i) => (
                <span key={s.id} className="flex items-center gap-1.5">
                  {i > 0 && <span className="text-[var(--color-text-faint)]">/</span>}
                  <button
                    onClick={() => setSelectedId(s.id)}
                    className={
                      i === crumbs.length - 1
                        ? "text-[var(--color-accent)]"
                        : "text-[var(--color-text-dim)] hover:text-[var(--color-text)]"
                    }
                  >
                    {s.name}
                  </button>
                </span>
              ))}
            </div>
          )}

          {/* filters */}
          {selectedId && (
            <div className="flex items-end gap-2">
              <div className="flex-1">
                <Field label="search this suite">
                  <Input
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder="name or id…"
                  />
                </Field>
              </div>
              <div className="w-36">
                <Field label="result">
                  <Select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
                    <option value="all">all</option>
                    <option value="pass">pass</option>
                    <option value="fail">fail</option>
                    <option value="blocked">blocked</option>
                    <option value="not_run">not run</option>
                  </Select>
                </Field>
              </div>
              <div className="w-36">
                <Field label="type">
                  <Select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
                    <option value="all">all</option>
                    <option value="automated">automated</option>
                    <option value="manual">manual</option>
                  </Select>
                </Field>
              </div>
            </div>
          )}

          <Panel title={selectedId ? `cases · ${filtered.length}` : "select a suite"} pad={false}>
            {!selectedId ? (
              <div className="p-4">
                <EmptyState title="no suite selected" hint="pick a suite on the left" />
              </div>
            ) : loadingCases ? (
              <div className="p-4">
                <Spinner label="loading cases" />
              </div>
            ) : filtered.length === 0 ? (
              <div className="p-4">
                <EmptyState title="no matching cases" hint={cases.length ? "adjust filters" : "empty suite"} />
              </div>
            ) : (
              <Table head={["id", "name", "latest result", "history", "type", "importance"]}>
                {filtered.map((c) => {
                  const st = caseStatus[String(c.id)];
                  return (
                    <Row key={c.id} onClick={() => router.push(`/cases/${c.id}`)}>
                      <Cell mono className="text-[var(--color-text-faint)]">
                        {c.external_id}
                      </Cell>
                      <Cell>
                        {c.name}
                        {c.current_version == null && (
                          <span className="ml-2 label !text-[var(--color-text-faint)]">no version</span>
                        )}
                      </Cell>
                      <Cell>
                        <StatusBadge status={st?.latest_status ?? "not_run"} />
                      </Cell>
                      <Cell>
                        <Sparkline points={(st?.recent ?? []).map((s) => ({ status: s }))} />
                      </Cell>
                      <Cell>
                        {c.current_version ? (
                          <span className="label">{c.current_version.execution_type}</span>
                        ) : (
                          <span className="mono text-[0.8125rem] text-[var(--color-text-faint)]">—</span>
                        )}
                      </Cell>
                      <Cell>
                        {c.current_version != null ? (
                          <Tag>{c.current_version.importance}</Tag>
                        ) : (
                          <span className="mono text-[0.8125rem] text-[var(--color-text-faint)]">—</span>
                        )}
                      </Cell>
                    </Row>
                  );
                })}
              </Table>
            )}
          </Panel>
        </div>
      </div>
    </div>
  );
}
