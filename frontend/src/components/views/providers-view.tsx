"use client";

import { useState } from "react";

import { PageHeading, StatusBadge, formatDate } from "@/components/ui";
import { api } from "@/lib/api";
import type { AppSnapshot, ProviderName } from "@/lib/types";

const providers: Array<{ id: ProviderName; mark: string; name: string; api: string }> = [
  { id: "openai", mark: "OA", name: "OpenAI", api: "Responses · Models API" },
  { id: "anthropic", mark: "AN", name: "Anthropic", api: "Messages · Models API" },
];

export function ProvidersView({ snapshot, refresh, notify }: { snapshot: AppSnapshot; refresh: () => Promise<void>; notify: (message: string) => void }) {
  const [busy, setBusy] = useState<ProviderName | null>(null);

  async function connect(provider: ProviderName, form: FormData) {
    setBusy(provider);
    try {
      await api.connectProvider(provider, String(form.get("apiKey")), form.get("validate") === "on");
      notify(`${provider} 키를 암호화 저장했습니다.`);
      await refresh();
    } catch (caught) {
      notify(caught instanceof Error ? caught.message : "Provider 연결에 실패했습니다.");
    } finally {
      setBusy(null);
    }
  }

  async function disconnect(provider: ProviderName) {
    if (!window.confirm(`${provider} 연결을 삭제할까요?`)) return;
    try {
      await api.deleteProvider(provider);
      notify(`${provider} 연결을 삭제했습니다.`);
      await refresh();
    } catch (caught) {
      notify(caught instanceof Error ? caught.message : "연결 삭제에 실패했습니다.");
    }
  }

  async function refreshModels(provider: ProviderName) {
    setBusy(provider);
    try {
      await api.refreshProvider(provider);
      notify(`${provider} 모델 목록을 갱신했습니다.`);
      await refresh();
    } catch (caught) {
      notify(caught instanceof Error ? caught.message : "모델 동기화에 실패했습니다.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="page">
      <PageHeading index="03" title="Bring your own" outline="intelligence." description="키는 브라우저에 보관하지 않고 서버로 한 번만 전송합니다. 응답에는 마스킹 값과 연결 상태만 표시됩니다." />
      <div className="vault-banner"><span className="vault-symbol">⌁</span><div><strong>PROVIDER VAULT / WRITE ONLY</strong><small>현재 PoC에는 인증이 없으므로 로컬에서만 사용하세요.</small></div><span>ENCRYPTED AT REST</span></div>
      <div className="provider-grid">
        {providers.map((definition) => {
          const connection = snapshot.providers.find((item) => item.provider === definition.id);
          return (
            <article className={`provider-card ${connection ? "connected" : ""}`} key={definition.id}>
              <div className="provider-head"><span className="provider-mark">{definition.mark}</span><div><h2>{definition.name}</h2><p>{definition.api}</p></div><StatusBadge tone={connection ? "ok" : "muted"}>{connection ? "CONNECTED" : "NOT CONNECTED"}</StatusBadge></div>
              {connection && <div className="provider-meta"><div><span>SECRET</span><strong>{connection.masked_key}</strong></div><div><span>MODELS</span><strong>{connection.models.length || "LOCAL"}</strong></div><div><span>VERIFIED</span><strong>{formatDate(connection.last_validated_at)}</strong></div></div>}
              <form onSubmit={(event) => { event.preventDefault(); void connect(definition.id, new FormData(event.currentTarget)); event.currentTarget.reset(); }}>
                <label className="field"><span>{connection ? "Replace API key" : "API key"}</span><input name="apiKey" type="password" minLength={8} autoComplete="new-password" placeholder="Write-only credential" required /></label>
                <label className="checkbox-row"><input type="checkbox" name="validate" defaultChecked /><span>Provider에서 실제 모델 목록 검증</span></label>
                <div className="provider-actions"><button className="button primary" disabled={busy === definition.id}>{busy === definition.id ? "Working…" : connection ? "Rotate key" : "Connect"}</button>{connection && <><button type="button" className="button" onClick={() => void refreshModels(definition.id)}>Refresh models</button><button type="button" className="text-button danger" onClick={() => void disconnect(definition.id)}>Disconnect</button></>}</div>
              </form>
            </article>
          );
        })}
      </div>
      <div className="section-title"><h2>Model catalog</h2><span>{snapshot.providers.reduce((sum, provider) => sum + provider.models.length, 0)} DISCOVERED</span></div>
      <div className="model-catalog">
        {snapshot.providers.flatMap((provider) => provider.models.map((model) => (
          <div className="model-row" key={`${provider.provider}-${model}`}><strong>{model}</strong><span>{provider.provider}</span><div><i>STREAM</i><i>TEXT</i><i>TOOLS</i></div></div>
        )))}
        {!snapshot.providers.some((provider) => provider.models.length) && <p className="catalog-note">로컬 bootstrap 연결은 모델 검증을 생략하므로 catalog가 비어 있습니다. Pipeline에는 `gpt-local-demo`를 사용할 수 있습니다.</p>}
      </div>
    </section>
  );
}
