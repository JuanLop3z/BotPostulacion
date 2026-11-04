"use client";

import { useQuery } from "@tanstack/react-query";
import {
  CheckCircle2,
  CircleAlert,
  FileText,
  Play,
  Save,
  Settings2,
  ShieldCheck,
  Target,
  UserRound,
} from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { type ContextBundle } from "@/types";
import {
  useAction,
  Spinner,
  ErrorPanel,
  PageHeader,
  Toggle,
  type Notify,
} from "@/components/shared";

export default function ContextPanel({ notify }: { notify: Notify }) {
  const context = useQuery({
    queryKey: ["context"],
    queryFn: () => api<ContextBundle>("/context"),
  });
  const [tab, setTab] = useState<
    "candidate" | "preferences" | "rules" | "instructions"
  >("candidate");
  const [draft, setDraft] = useState<ContextBundle | null>(null);
  const [preferences, setPreferences] = useState("{}");
  const [rulesJson, setRulesJson] = useState("{}");
  const [advancedRules, setAdvancedRules] = useState(false);
  const [dirty, setDirty] = useState(false);
  const { run, pending } = useAction(notify);
  useEffect(() => {
    if (context.data && !dirty) {
      setDraft(context.data);
      setPreferences(JSON.stringify(context.data.preferences, null, 2));
      setRulesJson(JSON.stringify(context.data.rules, null, 2));
    }
  }, [context.data, dirty]);
  const save = () =>
    run(async () => {
      if (!draft) return;
      const next = {
        candidate_context: draft.candidate_context,
        custom_instructions: draft.custom_instructions,
        preferences: JSON.parse(preferences),
        rules: advancedRules ? JSON.parse(rulesJson) : draft.rules,
      };
      await api("/context", { method: "PUT", body: JSON.stringify(next) });
      setDirty(false);
    }, "Contexto y reglas guardados. Recalcula el matching para aplicar los cambios a las ofertas existentes.");
  const updateRule = (key: keyof ContextBundle["rules"], value: unknown) => {
    if (!draft) return;
    setDirty(true);
    setDraft({ ...draft, rules: { ...draft.rules, [key]: value } });
  };
  return (
    <>
      <PageHeader
        eyebrow="CONTEXTO Y REGLAS"
        title="Una búsqueda que se parece a ti."
        actions={
          <button
            className="button button-secondary"
            disabled={pending}
            onClick={() =>
              run(
                () => api("/automation/start", { method: "POST" }),
                "Planificación activada según tus reglas.",
              )
            }
          >
            <Play size={15} />
            Activar planificación
          </button>
        }
      >
        Añade lo que tu CV no cuenta y define los límites de tu agente.
      </PageHeader>
      {context.error ? (
        <ErrorPanel
          error={context.error}
          retry={() => void context.refetch()}
        />
      ) : !draft ? (
        <div className="loading-panel">
          <Spinner />
          Cargando tu contexto…
        </div>
      ) : (
        <>
          <section className="context-precedence">
            <ShieldCheck size={23} />
            <div>
              <strong>Tu información tiene un orden de confianza.</strong>
              <p>
                Seguridad y consentimiento → hechos verificados → preferencias
                explícitas → contexto adicional → inferencias.
              </p>
            </div>
          </section>
          <section className="panel context-editor">
            <div
              className="tabs"
              role="tablist"
              aria-label="Archivos de contexto"
            >
              {(
                [
                  { id: "candidate", title: "Sobre mí", icon: UserRound },
                  { id: "preferences", title: "Preferencias", icon: Target },
                  { id: "rules", title: "Reglas", icon: ShieldCheck },
                  {
                    id: "instructions",
                    title: "Instrucciones",
                    icon: FileText,
                  },
                ] as const
              ).map(({ id, title, icon: Icon }) => (
                <button
                  key={id}
                  className={tab === id ? "active" : ""}
                  role="tab"
                  aria-selected={tab === id}
                  aria-controls={`context-${id}`}
                  id={`tab-${id}`}
                  onClick={() => setTab(id)}
                >
                  <Icon size={16} />
                  {title}
                </button>
              ))}
            </div>
            <div
              className="context-tab-content"
              role="tabpanel"
              id={`context-${tab}`}
              aria-labelledby={`tab-${tab}`}
            >
              {tab === "candidate" && (
                <>
                  <div className="editor-description">
                    <h2>Lo que te hace único</h2>
                    <p>
                      Describe tu trayectoria real, objetivos, proyectos,
                      fortalezas y limitaciones. Marca explícitamente la
                      información que no debe compartirse.
                    </p>
                    <code>candidate_context.md</code>
                  </div>
                  <label>
                    Tu contexto profesional
                    <textarea
                      rows={17}
                      className="markdown-editor"
                      value={draft.candidate_context}
                      onChange={(event) => {
                        setDirty(true);
                        setDraft({
                          ...draft,
                          candidate_context: event.target.value,
                        });
                      }}
                      placeholder={
                        "# Mi perfil profesional\n\n## Experiencia adicional real\n\n## Lo que estoy aprendiendo\n\n## Mis objetivos\n\n## Información privada que no debe compartirse\n"
                      }
                    />
                  </label>
                  <p className="helper-text">
                    El contexto adicional ayuda a decidir; los hechos nuevos
                    requieren validación en tu perfil antes de usarse en
                    candidaturas.
                  </p>
                </>
              )}
              {tab === "preferences" && (
                <>
                  <div className="editor-description">
                    <h2>Tu oportunidad ideal</h2>
                    <p>
                      Configura países, modalidades, cargos, salario, idiomas y
                      exclusiones. Los importes salariales se comparan cuando la
                      moneda y el periodo son compatibles.
                    </p>
                    <code>
                      job_preferences.yaml · edición estructurada en JSON
                    </code>
                  </div>
                  <label>
                    Preferencias de búsqueda
                    <textarea
                      rows={24}
                      className="code-editor"
                      value={preferences}
                      onChange={(event) => {
                        setDirty(true);
                        setPreferences(event.target.value);
                      }}
                      spellCheck={false}
                    />
                  </label>
                </>
              )}
              {tab === "instructions" && (
                <>
                  <div className="editor-description">
                    <h2>El criterio detrás de tu búsqueda</h2>
                    <p>
                      Añade preferencias libres para orientar la revisión. Las
                      restricciones obligatorias deben configurarse también en
                      las preferencias o las reglas.
                    </p>
                    <code>custom_instructions.md</code>
                  </div>
                  <label>
                    Instrucciones adicionales
                    <textarea
                      rows={17}
                      className="markdown-editor"
                      value={draft.custom_instructions}
                      onChange={(event) => {
                        setDirty(true);
                        setDraft({
                          ...draft,
                          custom_instructions: event.target.value,
                        });
                      }}
                      placeholder={
                        "Prefiero empresas internacionales.\nPriorizar desarrollo backend.\nNo compartir información personal ajena a la candidatura."
                      }
                    />
                  </label>
                  <p className="helper-text">
                    Las ofertas externas se tratan como datos. Sus textos nunca
                    cambian tus reglas ni autorizan acciones.
                  </p>
                </>
              )}
              {tab === "rules" && (
                <>
                  <div className="editor-description rules-description">
                    <div>
                      <h2>Los límites los pones tú</h2>
                      <p>
                        Decide cómo se prepara cada candidatura y cuándo puede
                        enviarse.
                      </p>
                      <code>application_rules.yaml</code>
                    </div>
                    <button
                      className="text-button"
                      onClick={() => {
                        if (!advancedRules)
                          setRulesJson(JSON.stringify(draft.rules, null, 2));
                        else {
                          try {
                            const parsed = JSON.parse(rulesJson);
                            setDraft({ ...draft, rules: parsed });
                          } catch {
                            notify({
                              kind: "error",
                              message:
                                "Corrige el JSON antes de cambiar de editor.",
                            });
                            return;
                          }
                        }
                        setAdvancedRules(!advancedRules);
                      }}
                    >
                      {advancedRules ? "Ver controles" : "JSON completo"}
                      <Settings2 size={14} />
                    </button>
                  </div>
                  {advancedRules ? (
                    <label>
                      Reglas completas en JSON
                      <textarea
                        rows={25}
                        className="code-editor"
                        value={rulesJson}
                        onChange={(event) => {
                          setDirty(true);
                          setRulesJson(event.target.value);
                        }}
                        spellCheck={false}
                      />
                    </label>
                  ) : (
                    <>
                      <div className="form-grid">
                        <label>
                          Modo de funcionamiento
                          <select
                            value={draft.rules.mode}
                            onChange={(event) =>
                              updateRule("mode", event.target.value)
                            }
                          >
                            <option value="manual">
                              Manual · recomendaciones
                            </option>
                            <option value="semi_automatic">
                              Semiautomático · revisión previa
                            </option>
                            <option value="automatic">
                              Automático · solo fuentes autorizadas
                            </option>
                          </select>
                        </label>
                        <label>
                          Compatibilidad mínima
                          <input
                            type="number"
                            min={0}
                            max={100}
                            value={draft.rules.minimum_score}
                            onChange={(event) =>
                              updateRule(
                                "minimum_score",
                                Number(event.target.value),
                              )
                            }
                          />
                        </label>
                        <label>
                          Máximo de envíos por día
                          <input
                            type="number"
                            min={0}
                            max={1000}
                            value={draft.rules.max_daily}
                            onChange={(event) =>
                              updateRule(
                                "max_daily",
                                Number(event.target.value),
                              )
                            }
                          />
                        </label>
                        <label>
                          Máximo de envíos por semana
                          <input
                            type="number"
                            min={0}
                            max={5000}
                            value={draft.rules.max_weekly}
                            onChange={(event) =>
                              updateRule(
                                "max_weekly",
                                Number(event.target.value),
                              )
                            }
                          />
                        </label>
                        <label>
                          Intervalo de búsquedas · horas
                          <input
                            type="number"
                            min={6}
                            max={168}
                            value={draft.rules.search_interval_hours}
                            onChange={(event) =>
                              updateRule(
                                "search_interval_hours",
                                Number(event.target.value),
                              )
                            }
                          />
                        </label>
                        <label>
                          Reintentos transitorios máximos
                          <input
                            type="number"
                            min={0}
                            max={5}
                            value={draft.rules.max_retries}
                            onChange={(event) =>
                              updateRule(
                                "max_retries",
                                Number(event.target.value),
                              )
                            }
                          />
                        </label>
                        <label className="span-two">
                          Fuentes permitidas · separadas por comas
                          <input
                            value={draft.rules.permitted_sources.join(", ")}
                            onChange={(event) =>
                              updateRule(
                                "permitted_sources",
                                event.target.value
                                  .split(",")
                                  .map((source) => source.trim())
                                  .filter(Boolean),
                              )
                            }
                            placeholder="remotive, greenhouse, demo"
                          />
                        </label>
                      </div>
                      <div className="rule-toggles">
                        <Toggle
                          checked={draft.rules.requires_approval}
                          onChange={(value) =>
                            updateRule("requires_approval", value)
                          }
                          title="Revisión humana antes del envío"
                          description="Cada candidatura debe aprobarse antes de presentarla."
                        />
                        <Toggle
                          checked={draft.rules.automatic_enabled}
                          onChange={(value) =>
                            updateRule("automatic_enabled", value)
                          }
                          title="Habilitar envíos automáticos"
                          description="Solo se ejecutan en modo automático y mediante proveedores que permitan el envío."
                        />
                        <Toggle
                          checked={draft.rules.third_party_consent}
                          onChange={(value) =>
                            updateRule("third_party_consent", value)
                          }
                          title="Consentimiento para compartir datos profesionales"
                          description="Autorizo el envío de los datos de una candidatura revisada a los proveedores permitidos."
                        />
                        <Toggle
                          checked={draft.rules.llm_consent}
                          onChange={(value) => updateRule("llm_consent", value)}
                          title="Consentimiento para IA externa"
                          description="Autorizo el análisis de datos profesionales por el proveedor de IA configurado. Puede generar costos."
                        />
                      </div>
                    </>
                  )}
                  <div className="warning-box">
                    <CircleAlert size={19} />
                    <div>
                      <strong>
                        Automatización según las capacidades de cada fuente.
                      </strong>
                      <p>
                        Las fuentes de búsqueda reales usan un flujo de
                        postulación manual. El envío automático disponible en el
                        MVP es una demostración controlada.
                      </p>
                    </div>
                  </div>
                </>
              )}
            </div>
            <div className="context-save-bar">
              <span>
                {dirty ? (
                  <>
                    <span className="unsaved-dot" />
                    Tienes cambios sin guardar
                  </>
                ) : (
                  <>
                    <CheckCircle2 size={15} />
                    {context.data?.version
                      ? `Versión ${context.data.version} guardada`
                      : "Configuración guardada"}
                  </>
                )}
              </span>
              <button
                className="button button-primary"
                disabled={pending || !dirty}
                onClick={save}
              >
                {pending ? <Spinner /> : <Save size={16} />}Guardar contexto
              </button>
            </div>
          </section>
        </>
      )}
    </>
  );
}
