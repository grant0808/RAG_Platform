"use client";

import { useState } from "react";

import { PageHeading, StatusBadge, formatDate } from "@/components/ui";
import { api } from "@/lib/api";
import type { AppSnapshot, ProviderName } from "@/lib/types";

const providers: Array<{ id: ProviderName; mark: string; name: string; api: string }> = [
  { id: "openai", mark: "OA", name: "OpenAI", api: "Responses + Models API" },
  { id: "anthropic", mark: "AN", name: "Anthropic", api: "Messages + Models API" },
];

export function ProvidersView({
  snapshot,
  refresh,
  notify,
}: {
  snapshot: AppSnapshot;
  refresh: () => Promise<void>;
  notify: (message: string) => void;
}) {
  const [busy, setBusy] = useState<ProviderName | null>(null);

  async function connect(provider: ProviderName, form: FormData) {
    setBusy(provider);
    try {
      await api.connectProvider(provider, String(form.get("apiKey")), form.get("validate") === "on");
      notify(`${provider} credential을 저장했습니다.`);
      await refresh();
    } catch (caught) {
      notify(caught instanceof Error ? caught.message : "Provider 연결에 실패했습니다.");
    } finally {
      setBusy(null);
    }
  }

  async function disconnect(provider: ProviderName) {
    if (!window.confirm(`${provider} 연결을 해제할까요?`)) return;
    try {
      await api.deleteProvider(provider);
      notify(`${provider} 연결을 해제했습니다.`);
      await refresh();
    } catch (caught) {
      notify(caught instanceof Error ? caught.message : "연결 해제에 실패했습니다.");
    }
  }

  async function refreshModels(provider: ProviderName) {
    setBusy(provider);
    try {
      await api.refreshProvider(provider);
      notify(`${provider} model catalog를 갱신했습니다.`);
      await refresh();
    } catch (caught) {
      notify(caught instanceof Error ? caught.message : "Model refresh에 실패했습니다.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="page">
      <PageHeading
        index="03"
        title="Bring your own"
        outline="intelligence."
        description="Provider key는 backend로만 전송되고 암호화 저장됩니다. 응답에는 masked secret만 노출하며, local fake mode에서는 실제 API 호출 없이도 실행할 수 있습니다."
      />
      <div className="vault-banner">
        <span className="vault-symbol">KEY</span>
        <div>
          <strong>PROVIDER VAULT / WRITE ONLY</strong>
          <small>현재 local PoC는 auth가 꺼져 있습니다. 개인 로컬 환경에서만 사용하세요.</small>
        </div>
        <span>ENCRYPTED AT REST</span>
      </div>
      <div className="provider-grid">
        {providers.map((definition) => {
          const connection = snapshot.providers.find((item) => item.provider === definition.id);
          return (
            <article className={`provider-card ${connection ? "connected" : ""}`} key={definition.id}>
              <div className="provider-head">
                <span className="provider-mark">{definition.mark}</span>
                <div>
                  <h2>{definition.name}</h2>
                  <p>{definition.api}</p>
                </div>
                <StatusBadge tone={connection ? "ok" : "muted"}>
                  {connection ? "CONNECTED" : "NOT CONNECTED"}
                </StatusBadge>
              </div>
              {connection && (
                <div className="provider-meta">
                  <div>
                    <span>SECRET</span>
                    <strong>{connection.masked_key}</strong>
                  </div>
                  <div>
                    <span>MODELS</span>
                    <strong>{connection.models.length || "LOCAL"}</strong>
                  </div>
                  <div>
                    <span>VERIFIED</span>
                    <strong>{formatDate(connection.last_validated_at)}</strong>
                  </div>
                </div>
              )}
              <form
                onSubmit={(event) => {
                  event.preventDefault();
                  void connect(definition.id, new FormData(event.currentTarget));
                  event.currentTarget.reset();
                }}
              >
                <label className="field">
                  <span>{connection ? "Rotate API key" : "API key"}</span>
                  <input
                    name="apiKey"
                    type="password"
                    minLength={8}
                    autoComplete="new-password"
                    placeholder="저장 후 다시 표시하지 않습니다"
                    required
                  />
                </label>
                <label className="checkbox-row">
                  <input type="checkbox" name="validate" defaultChecked />
                  <span>
                    {definition.id === "ollama"
                      ? "Local Ollama /api/tags로 model list 검증"
                      : "Provider model API로 실제 model list 검증"}
                  </span>
                </label>
                <div className="provider-actions">
                  <button className="button primary" disabled={busy === definition.id}>
                    {busy === definition.id ? "Working..." : connection ? "Rotate key" : "Connect"}
                  </button>
                  {connection && (
                    <>
                      <button type="button" className="button" onClick={() => void refreshModels(definition.id)}>
                        Refresh models
                      </button>
                      <button type="button" className="text-button danger" onClick={() => void disconnect(definition.id)}>
                        Disconnect
                      </button>
                    </>
                  )}
                </div>
              </form>
            </article>
          );
        })}
      </div>
      <div className="section-title">
        <h2>Model catalog</h2>
        <span>{snapshot.providers.reduce((sum, provider) => sum + provider.models.length, 0)} DISCOVERED</span>
      </div>
      <div className="model-catalog">
        {snapshot.providers.flatMap((provider) =>
          provider.models.map((model) => (
            <div className="model-row" key={`${provider.provider}-${model}`}>
              <strong>{model}</strong>
              <span>{provider.provider}</span>
              <div>
                <i>streaming</i>
                <i>text</i>
                <i>reasoning</i>
              </div>
            </div>
          )),
        )}
        {!snapshot.providers.some((provider) => provider.models.length) && (
          <p className="catalog-note">
            Local bootstrap에서는 model 검증을 생략할 수 있어 catalog가 비어 있을 수 있습니다.
            fake LLM mode가 켜져 있으면 pipeline은 `gpt-local-demo`를 계속 사용할 수 있습니다.
          </p>
        )}
      </div>
    </section>
  );
}
