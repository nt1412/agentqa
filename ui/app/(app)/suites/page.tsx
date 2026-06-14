"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useApp } from "@/app/providers";
import { api } from "@/lib/api";
import type { Suite, TestCase } from "@/lib/types";
import {
  Button,
  Cell,
  EmptyState,
  Field,
  Input,
  Panel,
  Row,
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
    if (s.parent_id === null) {
      roots.push(node);
    } else {
      map.get(s.parent_id)?.children.push(node);
    }
  }

  const sortNodes = (nodes: TreeNode[]) => {
    nodes.sort((a, b) => a.order - b.order);
    for (const n of nodes) sortNodes(n.children);
  };
  sortNodes(roots);
  return roots;
}

/* ---------- tree renderer ---------- */

function SuiteRow({
  node,
  depth,
  selectedId,
  onSelect,
}: {
  node: TreeNode;
  depth: number;
  selectedId: number | null;
  onSelect: (id: number) => void;
}) {
  const isSelected = node.id === selectedId;
  return (
    <>
      <button
        onClick={() => onSelect(node.id)}
        className={`w-full text-left px-3 py-2 mono text-[0.8125rem] flex items-center gap-2 border-b border-[var(--color-border)] transition-colors hover:bg-[var(--color-bg-elev-2)] ${
          isSelected ? "bg-[var(--color-bg-elev-2)] text-[var(--color-accent)]" : "text-[var(--color-text)]"
        }`}
        style={{ paddingLeft: `${12 + depth * 16}px` }}
      >
        {depth > 0 && (
          <span className="text-[var(--color-text-faint)]">└</span>
        )}
        <span className="truncate">{node.name}</span>
        {node.children.length > 0 && (
          <span className="ml-auto label text-[var(--color-text-faint)]">{node.children.length}</span>
        )}
      </button>
      {node.children.map((child) => (
        <SuiteRow
          key={child.id}
          node={child}
          depth={depth + 1}
          selectedId={selectedId}
          onSelect={onSelect}
        />
      ))}
    </>
  );
}

/* ---------- new suite form ---------- */

function NewSuiteForm({
  onSubmit,
  disabled,
}: {
  onSubmit: (name: string) => Promise<void>;
  disabled?: boolean;
}) {
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);

  async function handleSubmit() {
    const trimmed = name.trim();
    if (!trimmed) return;
    setSaving(true);
    try {
      await onSubmit(trimmed);
      setName("");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="flex items-end gap-2">
      <div className="flex-1">
        <Field label="new suite">
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
            placeholder="suite name"
            disabled={saving || disabled}
          />
        </Field>
      </div>
      <Button onClick={handleSubmit} disabled={saving || !name.trim() || disabled}>
        {saving ? "saving…" : "add"}
      </Button>
    </div>
  );
}

/* ---------- main page ---------- */

export default function SuitesPage() {
  const { currentProject } = useApp();
  const router = useRouter();

  const [suites, setSuites] = useState<Suite[]>([]);
  const [loadingSuites, setLoadingSuites] = useState(true);
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const [cases, setCases] = useState<TestCase[]>([]);
  const [loadingCases, setLoadingCases] = useState(false);

  // Load suites when project changes; reset selection
  useEffect(() => {
    if (!currentProject) return;
    setSelectedId(null);
    setSuites([]);
    setLoadingSuites(true);
    (async () => {
      try {
        const data = await api.suites(currentProject.id);
        setSuites(data);
      } finally {
        setLoadingSuites(false);
      }
    })();
  }, [currentProject]);

  // Load cases when suite selection changes
  useEffect(() => {
    if (selectedId === null) {
      setCases([]);
      return;
    }
    setLoadingCases(true);
    (async () => {
      try {
        const data = await api.suiteCases(selectedId);
        setCases(data);
      } finally {
        setLoadingCases(false);
      }
    })();
  }, [selectedId]);

  async function handleCreateSuite(name: string) {
    if (!currentProject) return;
    await api.createSuite(currentProject.id, name);
    const fresh = await api.suites(currentProject.id);
    setSuites(fresh);
  }

  if (!currentProject) return <EmptyState title="no project selected" hint="create one in Admin" />;

  const tree = buildTree(suites);

  return (
    <div className="space-y-6">
      {/* Page heading */}
      <div>
        <h1 className="mono text-lg font-semibold tracking-wide">test suites</h1>
        <p className="label mt-0.5">{currentProject.prefix} · suite browser</p>
      </div>

      <div className="grid grid-cols-[280px_1fr] gap-6 items-start">
        {/* Left: suite tree */}
        <Panel title="suites">
          <div className="space-y-3 mb-3">
            <NewSuiteForm onSubmit={handleCreateSuite} />
          </div>
          {loadingSuites ? (
            <Spinner label="loading suites" />
          ) : tree.length === 0 ? (
            <EmptyState title="no suites" hint="create one above" />
          ) : (
            <div className="border border-[var(--color-border)] -mx-4 mt-4">
              {tree.map((node) => (
                <SuiteRow
                  key={node.id}
                  node={node}
                  depth={0}
                  selectedId={selectedId}
                  onSelect={setSelectedId}
                />
              ))}
            </div>
          )}
        </Panel>

        {/* Right: cases in selected suite */}
        <Panel title={selectedId ? "test cases" : "select a suite"} pad={false}>
          {!selectedId ? (
            <div className="p-4">
              <EmptyState title="no suite selected" hint="click a suite on the left to view its cases" />
            </div>
          ) : loadingCases ? (
            <div className="p-4">
              <Spinner label="loading cases" />
            </div>
          ) : cases.length === 0 ? (
            <div className="p-4">
              <EmptyState title="no cases in this suite" />
            </div>
          ) : (
            <Table head={["id", "name", "importance", "type", "status"]}>
              {cases.map((c) => (
                <Row key={c.id} onClick={() => router.push(`/cases/${c.id}`)}>
                  <Cell mono className="text-[var(--color-text-faint)]">
                    {c.external_id}
                  </Cell>
                  <Cell>{c.name}</Cell>
                  <Cell>
                    {c.current_version != null ? (
                      <Tag>{c.current_version.importance}</Tag>
                    ) : (
                      <span className="text-[var(--color-text-faint)] mono text-[0.8125rem]">—</span>
                    )}
                  </Cell>
                  <Cell>
                    {c.current_version != null ? (
                      <span className="label">{c.current_version.execution_type}</span>
                    ) : (
                      <span className="text-[var(--color-text-faint)] mono text-[0.8125rem]">—</span>
                    )}
                  </Cell>
                  <Cell>
                    {c.current_version != null ? (
                      <StatusBadge status={c.current_version.status} />
                    ) : (
                      <span className="text-[var(--color-text-faint)] mono text-[0.8125rem]">—</span>
                    )}
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
