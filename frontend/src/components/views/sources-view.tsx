"use client";

import { useRef, useState } from "react";

import { EmptyState, PageHeading, StatusBadge, formatBytes, formatDate } from "@/components/ui";
import { api } from "@/lib/api";
import type { AppSnapshot } from "@/lib/types";

export function SourcesView({ snapshot, refresh, notify }: { snapshot: AppSnapshot; refresh: () => Promise<void>; notify: (message: string) => void }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const totalSize = snapshot.sources.reduce((total, source) => total + source.size_bytes, 0);
  const tables = snapshot.sources.filter((source) => source.kind === "table").length;

  async function upload(file: File) {
    setUploading(true);
    try {
      const source = await api.uploadSource(file);
      notify(`${source.name}을 인덱싱했습니다.`);
      await refresh();
    } catch (caught) {
      notify(caught instanceof Error ? caught.message : "업로드에 실패했습니다.");
    } finally {
      setUploading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  async function remove(id: string, name: string) {
    if (!window.confirm(`${name}과 관련 인덱스를 삭제할까요?`)) return;
    try {
      await api.deleteSource(id);
      notify(`${name}을 삭제했습니다.`);
      await refresh();
    } catch (caught) {
      notify(caught instanceof Error ? caught.message : "삭제에 실패했습니다.");
    }
  }

  return (
    <section className="page">
      <PageHeading index="02" title="Connect every" outline="source." description="파일은 업로드 즉시 문서 chunk 또는 TAG 테이블로 변환되며 실행 가능한 상태가 응답으로 확정됩니다." action={<><input ref={inputRef} className="visually-hidden" type="file" accept=".txt,.md,.json,.html,.pdf,.csv,.xlsx,.xlsm" onChange={(event) => event.target.files?.[0] && void upload(event.target.files[0])} /><button className="button primary" disabled={uploading} onClick={() => inputRef.current?.click()}>{uploading ? "Processing…" : "+ Upload source"}</button></>} />
      <div className="source-summary">
        <div><strong>{snapshot.sources.length}</strong><span>Ready sources</span></div>
        <div><strong>{tables}</strong><span>TAG tables</span></div>
        <div><strong>{formatBytes(totalSize)}</strong><span>Original data</span></div>
      </div>
      <div className="drop-zone" onDragOver={(event) => event.preventDefault()} onDrop={(event) => { event.preventDefault(); const file = event.dataTransfer.files[0]; if (file) void upload(file); }}>
        <span>DROP / KNOWLEDGE</span><strong>문서 또는 테이블을 여기에 놓으세요.</strong><small>TXT · MD · JSON · HTML · PDF · CSV · XLSX · XLSM / 최대 20 MiB</small>
      </div>
      <div className="section-title"><h2>Source registry</h2><span>{snapshot.sources.length} READY</span></div>
      {snapshot.sources.length === 0 ? <EmptyState title="아직 연결된 소스가 없습니다.">첫 문서나 표를 업로드해 RAG·TAG를 시작하세요.</EmptyState> : (
        <div className="source-list">
          {snapshot.sources.map((source, index) => (
            <article className="source-row" key={source.id}>
              <span className="source-index">{String(index + 1).padStart(2, "0")}</span>
              <div className="source-kind">{source.kind === "table" ? "▦" : "▤"}</div>
              <div className="source-name"><strong>{source.name}</strong><span>{source.table_name ?? `${source.chunk_count} chunks`}</span></div>
              <div><StatusBadge>{source.status.toUpperCase()}</StatusBadge></div>
              <div className="source-meta"><span>{formatBytes(source.size_bytes)}</span><small>{formatDate(source.created_at)}</small></div>
              <button className="icon-danger" onClick={() => void remove(source.id, source.name)} aria-label={`${source.name} 삭제`}>×</button>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
