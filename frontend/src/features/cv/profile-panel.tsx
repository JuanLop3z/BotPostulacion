"use client";

import { useQuery } from "@tanstack/react-query";
import {
  BadgeCheck,
  Check,
  CheckCircle2,
  Clock3,
  Plus,
  Save,
  Settings2,
  ShieldCheck,
  Upload,
  UserRound,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { type CandidateProfile, type ProfileRecord } from "@/types";
import {
  useAction,
  Spinner,
  Badge,
  Empty,
  ErrorPanel,
  PageHeader,
  type Notify,
} from "@/components/shared";

const emptyProfile: CandidateProfile = {
  full_name: "",
  email: "",
  phone: "",
  location: "",
  title: "",
  skills: [],
  experience_years: null,
  seniority: null,
  languages: {},
  education: [],
  certifications: [],
  projects: [],
  summary: "",
  facts: [],
  reviewed: false,
};

export default function ProfilePanel({ notify }: { notify: Notify }) {
  const profile = useQuery({
    queryKey: ["profile"],
    queryFn: () => api<ProfileRecord | null>("/profile"),
  });
  const [draft, setDraft] = useState<CandidateProfile | null>(null);
  const [skills, setSkills] = useState("");
  const [languages, setLanguages] = useState("{}");
  const [advanced, setAdvanced] = useState(false);
  const [advancedText, setAdvancedText] = useState("");
  const [dragging, setDragging] = useState(false);
  const [dirty, setDirty] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const { run, pending } = useAction(notify);
  useEffect(() => {
    if (!profile.isPending && !profile.error && !dirty) {
      const next = profile.data?.profile ?? emptyProfile;
      setDraft(next);
      setSkills(next.skills.join(", "));
      setLanguages(JSON.stringify(next.languages, null, 2));
      setAdvancedText(JSON.stringify(next, null, 2));
    }
  }, [profile.data, profile.isPending, profile.error, dirty]);
  const update = <K extends keyof CandidateProfile>(
    field: K,
    value: CandidateProfile[K],
  ) => {
    if (!draft) return;
    setDirty(true);
    setDraft({ ...draft, [field]: value });
  };
  const toggleAdvanced = () => {
    if (!draft) return;
    try {
      if (advanced) {
        const parsed = JSON.parse(advancedText) as CandidateProfile;
        if (
          !Array.isArray(parsed.skills) ||
          !parsed.languages ||
          typeof parsed.languages !== "object"
        )
          throw new Error(
            "El perfil debe incluir habilidades e idiomas válidos.",
          );
        setDraft(parsed);
        setSkills(parsed.skills.join(", "));
        setLanguages(JSON.stringify(parsed.languages, null, 2));
      } else {
        setAdvancedText(
          JSON.stringify(
            {
              ...draft,
              skills: skills
                .split(",")
                .map((skill) => skill.trim())
                .filter(Boolean),
              languages: JSON.parse(languages),
            },
            null,
            2,
          ),
        );
      }
      setAdvanced(!advanced);
    } catch (error) {
      notify({
        kind: "error",
        message:
          error instanceof Error ? error.message : "Revisa el JSON del perfil.",
      });
    }
  };
  const upload = async (file?: File) => {
    if (!file) return;
    if (!/\.(pdf|docx|txt)$/i.test(file.name)) {
      notify({ kind: "error", message: "Elige un archivo PDF, DOCX o TXT." });
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      notify({
        kind: "error",
        message: "El archivo debe pesar como máximo 10 MB.",
      });
      return;
    }
    await run(async () => {
      const form = new FormData();
      form.append("file", file);
      await api<ProfileRecord>("/cv", { method: "POST", body: form });
      setDirty(false);
    }, "Hoja de vida procesada. Revisa los datos extraídos antes de aprobarlos.");
    if (fileInput.current) fileInput.current.value = "";
  };
  const save = async (review: boolean) => {
    if (!draft) return;
    await run(
      async () => {
        let nextProfile: CandidateProfile;
        if (advanced)
          nextProfile = JSON.parse(advancedText) as CandidateProfile;
        else
          nextProfile = {
            ...draft,
            skills: skills
              .split(",")
              .map((skill) => skill.trim())
              .filter(Boolean),
            languages: JSON.parse(languages) as Record<string, string>,
          };
        await api("/profile", {
          method: "PUT",
          body: JSON.stringify({ profile: nextProfile }),
        });
        if (review) await api("/profile/review", { method: "POST" });
        setDirty(false);
      },
      review
        ? "Perfil revisado y aprobado. Ya puedes preparar candidaturas."
        : "Nueva versión de tu perfil guardada.",
    );
  };
  return (
    <>
      <PageHeader
        eyebrow="MI PERFIL"
        title="Tu experiencia, con tu propia voz."
        actions={
          profile.data && (
            <Badge tone={profile.data.reviewed ? "teal" : "orange"}>
              {profile.data.reviewed ? (
                <CheckCircle2 size={13} />
              ) : (
                <Clock3 size={13} />
              )}
              {profile.data.reviewed ? "Revisado" : "Pendiente de revisión"} · v
              {profile.data.version}
            </Badge>
          )
        }
      >
        Completa tus datos directamente o carga tu CV para extraerlos. Confirma
        la información antes de usarla en una candidatura.
      </PageHeader>
      <section
        className={`upload-zone ${dragging ? "dragging" : ""}`}
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          if (!pending) void upload(event.dataTransfer.files[0]);
        }}
      >
        <span className="upload-icon">
          <Upload size={25} />
        </span>
        <div>
          <h2>
            {pending ? "Procesando tu documento…" : "Sube tu hoja de vida"}
          </h2>
          <p>Arrastra tu archivo aquí o selecciónalo desde tu equipo.</p>
          <span>PDF, DOCX o TXT · Máximo 10 MB · Extracción sin OCR</span>
        </div>
        <input
          ref={fileInput}
          type="file"
          className="sr-only"
          accept=".pdf,.docx,.txt"
          onChange={(event) => void upload(event.target.files?.[0])}
          disabled={pending}
        />
        <button
          className="button button-primary"
          disabled={pending}
          onClick={() => fileInput.current?.click()}
        >
          {pending ? <Spinner /> : <Plus size={17} />}Elegir archivo
        </button>
      </section>
      {profile.error ? (
        <ErrorPanel
          error={profile.error}
          retry={() => void profile.refetch()}
        />
      ) : profile.isPending ? (
        <div className="loading-panel">
          <Spinner />
          Cargando perfil…
        </div>
      ) : draft ? (
        <section className="panel profile-editor">
          <div className="panel-heading">
            <div>
              <h2>Perfil profesional</h2>
              <p>La información desconocida puede permanecer vacía.</p>
            </div>
            <div className="editor-tools">
              <button
                className="text-button"
                disabled={pending || dirty || !profile.data}
                title={
                  dirty
                    ? "Guarda tus cambios antes de incorporar contexto"
                    : "Proponer datos adicionales para revisar"
                }
                onClick={() =>
                  run(
                    () => api("/profile/enrich", { method: "POST" }),
                    "Contexto incorporado como propuestas pendientes de validar.",
                  )
                }
              >
                <Plus size={14} />
                Incorporar contexto
              </button>
              <button className="text-button" onClick={toggleAdvanced}>
                {advanced ? "Editor de campos" : "Editar JSON completo"}
                <Settings2 size={14} />
              </button>
            </div>
          </div>
          {advanced ? (
            <label className="advanced-label">
              Perfil completo en JSON
              <textarea
                className="code-editor"
                value={advancedText}
                onChange={(event) => {
                  setDirty(true);
                  setAdvancedText(event.target.value);
                }}
                rows={24}
                spellCheck={false}
              />
            </label>
          ) : (
            <>
              <div className="form-grid">
                <label>
                  Nombre completo
                  <input
                    value={draft.full_name || ""}
                    onChange={(event) =>
                      update("full_name", event.target.value)
                    }
                    autoComplete="name"
                  />
                </label>
                <label>
                  Título profesional
                  <input
                    value={draft.title || ""}
                    onChange={(event) => update("title", event.target.value)}
                    placeholder="Ej. Backend Developer"
                  />
                </label>
                <label>
                  Correo electrónico
                  <input
                    type="email"
                    value={draft.email || ""}
                    onChange={(event) => update("email", event.target.value)}
                    autoComplete="email"
                  />
                </label>
                <label>
                  Teléfono
                  <input
                    value={draft.phone || ""}
                    onChange={(event) => update("phone", event.target.value)}
                    autoComplete="tel"
                  />
                </label>
                <label>
                  Ubicación
                  <input
                    value={draft.location || ""}
                    onChange={(event) => update("location", event.target.value)}
                    placeholder="Ciudad, país"
                  />
                </label>
                <label>
                  Años de experiencia confirmados
                  <input
                    type="number"
                    min={0}
                    max={80}
                    step={0.5}
                    value={draft.experience_years ?? ""}
                    onChange={(event) =>
                      update(
                        "experience_years",
                        event.target.value ? Number(event.target.value) : null,
                      )
                    }
                    placeholder="Sin confirmar"
                  />
                </label>
                <label>
                  Seniority
                  <input
                    value={draft.seniority || ""}
                    onChange={(event) =>
                      update("seniority", event.target.value || null)
                    }
                    placeholder="Sin confirmar"
                  />
                </label>
                <label>
                  Habilidades separadas por comas
                  <input
                    value={skills}
                    onChange={(event) => {
                      setSkills(event.target.value);
                      setDirty(true);
                    }}
                    placeholder="Python, FastAPI, PostgreSQL"
                  />
                </label>
              </div>
              <label className="wide-label">
                Resumen profesional
                <textarea
                  rows={4}
                  value={draft.summary || ""}
                  onChange={(event) => update("summary", event.target.value)}
                />
              </label>
              <div className="form-grid">
                <label>
                  Educación · una entrada por línea
                  <textarea
                    rows={4}
                    value={(draft.education || []).join("\n")}
                    onChange={(event) =>
                      update(
                        "education",
                        event.target.value.split("\n").filter(Boolean),
                      )
                    }
                  />
                </label>
                <label>
                  Certificaciones · una por línea
                  <textarea
                    rows={4}
                    value={(draft.certifications || []).join("\n")}
                    onChange={(event) =>
                      update(
                        "certifications",
                        event.target.value.split("\n").filter(Boolean),
                      )
                    }
                  />
                </label>
                <label>
                  Proyectos · uno por línea
                  <textarea
                    rows={4}
                    value={(draft.projects || []).join("\n")}
                    onChange={(event) =>
                      update(
                        "projects",
                        event.target.value.split("\n").filter(Boolean),
                      )
                    }
                  />
                </label>
                <label>
                  Idiomas y nivel confirmado · JSON
                  <textarea
                    rows={4}
                    className="code-editor compact-code"
                    value={languages}
                    onChange={(event) => {
                      setLanguages(event.target.value);
                      setDirty(true);
                    }}
                    spellCheck={false}
                  />
                  <small>
                    Ejemplo: {`{"english": "B2", "spanish": "native"}`}
                  </small>
                </label>
              </div>
              {draft.facts?.length > 0 && (
                <details className="fact-details">
                  <summary>
                    Ver trazabilidad de los datos{" "}
                    <span>{draft.facts.length} hechos</span>
                  </summary>
                  <div className="table-scroll">
                    <table>
                      <thead>
                        <tr>
                          <th>CAMPO</th>
                          <th>VALOR</th>
                          <th>ORIGEN</th>
                          <th>EVIDENCIA</th>
                          <th>VALIDACIÓN</th>
                        </tr>
                      </thead>
                      <tbody>
                        {draft.facts.map((fact, index) => (
                          <tr key={index}>
                            <td>{fact.field}</td>
                            <td>
                              {typeof fact.value === "string"
                                ? fact.value
                                : JSON.stringify(fact.value)}
                            </td>
                            <td>
                              <Badge tone={fact.verified ? "teal" : "orange"}>
                                {{
                                  cv: "CV",
                                  context: "Contexto",
                                  inference: "Inferencia",
                                  user: "Usuario",
                                }[fact.source] || fact.source}
                                {fact.verified && <Check size={11} />}
                              </Badge>
                            </td>
                            <td className="evidence-cell">{fact.evidence}</td>
                            <td>
                              {!fact.verified && (
                                <button
                                  className="text-button"
                                  disabled={pending || dirty}
                                  onClick={() =>
                                    run(async () => {
                                      await api("/profile/verify-fact", {
                                        method: "POST",
                                        body: JSON.stringify({
                                          field: fact.field,
                                          value: fact.value,
                                        }),
                                      });
                                      setDirty(false);
                                    }, "Dato confirmado. Revisa y aprueba la nueva versi\u00f3n del perfil.")
                                  }
                                >
                                  <Check size={13} />
                                  Confirmar dato
                                </button>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </details>
              )}
            </>
          )}
          <div className="review-callout">
            <ShieldCheck size={21} />
            <div>
              <strong>
                Confirma únicamente experiencia y conocimientos reales.
              </strong>
              <p>
                Al aprobar el perfil, confirmas que revisaste sus datos y que
                pueden usarse para preparar candidaturas.
              </p>
            </div>
          </div>
          <div className="form-actions">
            <button
              className="button button-secondary"
              disabled={pending}
              onClick={() => save(false)}
            >
              <Save size={16} />
              Guardar cambios
            </button>
            <button
              className="button button-primary"
              disabled={pending}
              onClick={() => save(true)}
            >
              {pending ? <Spinner /> : <BadgeCheck size={17} />}Guardar y
              aprobar perfil
            </button>
          </div>
        </section>
      ) : (
        <section className="panel">
          <Empty icon={UserRound} title="Tu perfil comienza con tu CV">
            Sube una hoja de vida para extraer tus habilidades y datos
            profesionales. Tendrás la oportunidad de revisar y corregir cada
            campo.
          </Empty>
        </section>
      )}
    </>
  );
}
