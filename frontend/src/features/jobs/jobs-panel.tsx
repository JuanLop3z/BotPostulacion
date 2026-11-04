"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  ArrowUpRight,
  BriefcaseBusiness,
  CheckCircle2,
  CircleAlert,
  ClipboardPaste,
  FileText,
  Filter,
  Globe2,
  MapPin,
  RefreshCw,
  Search,
} from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, safeExternalUrl } from "@/lib/api";
import { type Job, type Source, type Task } from "@/types";
import {
  formatDate,
  money,
  useAction,
  Spinner,
  Badge,
  Empty,
  ErrorPanel,
  PageHeader,
  CompanyMark,
  Modal,
  type Section,
  type Notify,
  modeLabels,
  isCompleteTask,
  stateLabels,
} from "@/components/shared";
import AssistedImportDialog from "@/features/jobs/assisted-import-dialog";

export default function JobsPanel({
  notify,
  go,
}: {
  notify: Notify;
  go: (section: Section) => void;
}) {
  const client = useQueryClient();
  const [source, setSource] = useState("remotive");
  const [query, setQuery] = useState("");
  const [board, setBoard] = useState("");
  const [taskId, setTaskId] = useState<string | null>(null);
  const [selected, setSelected] = useState<Job | null>(null);
  const [importOpen, setImportOpen] = useState(false);
  const [importDraft, setImportDraft] = useState<Job | null>(null);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [filters, setFilters] = useState({
    q: "",
    min_score: "",
    work_mode: "",
    company: "",
    location: "",
    technology: "",
    salary_min: "",
    status: "",
    published_after: "",
  });
  const [activeFilters, setActiveFilters] = useState(filters);
  const sources = useQuery({
    queryKey: ["sources"],
    queryFn: () => api<Source[]>("/sources"),
  });
  const params = new URLSearchParams(
    Object.entries(activeFilters).filter(([, value]) => Boolean(value)),
  ).toString();
  const jobs = useQuery({
    queryKey: ["jobs", params],
    queryFn: () => api<Job[]>(`/jobs?${params}`),
  });
  const { pending, run } = useAction(notify);
  const task = useQuery({
    queryKey: ["task", taskId],
    queryFn: () => api<Task>(`/tasks/${taskId}`),
    enabled: Boolean(taskId),
    refetchInterval: (current) =>
      current.state.data && isCompleteTask(current.state.data.status)
        ? false
        : 1500,
  });
  const reportedTask = useRef("");
  useEffect(() => {
    if (
      !task.data ||
      !isCompleteTask(task.data.status) ||
      reportedTask.current === task.data.id
    )
      return;
    reportedTask.current = task.data.id;
    void client.invalidateQueries({ queryKey: ["jobs"] });
    void client.invalidateQueries({ queryKey: ["dashboard"] });
    notify(
      task.data.error
        ? { kind: "error", message: task.data.error }
        : {
            kind: "success",
            message:
              "Búsqueda terminada. Tus oportunidades están actualizadas.",
          },
    );
  }, [task.data, client, notify]);
  const searching = Boolean(
    taskId && (!task.data || !isCompleteTask(task.data.status)) && !task.error,
  );
  const search = async (event: FormEvent) => {
    event.preventDefault();
    await run(async () => {
      const result = await api<{ task_id: string; status: string }>(
        "/jobs/search",
        {
          method: "POST",
          body: JSON.stringify({ source, query, ...(board ? { board } : {}) }),
        },
      );
      setTaskId(result.task_id);
    });
  };
  const prepare = async (job: Job) => {
    await run(async () => {
      await api("/applications", {
        method: "POST",
        body: JSON.stringify({ job_id: job.id }),
      });
      setSelected(null);
      go("applications");
    }, "Candidatura preparada. Revísala antes de continuar.");
  };
  return (
    <>
      <PageHeader
        eyebrow="OPORTUNIDADES"
        title="Encuentra un lugar para tu talento."
        actions={
          <>
            <button
              className="button button-primary"
              onClick={() => {
                setImportDraft(null);
                setImportOpen(true);
              }}
            >
              <ClipboardPaste size={16} />
              Importar oferta
            </button>
            <button
              className="button button-secondary"
              disabled={pending}
              onClick={() =>
                run(
                  () => api("/jobs/rematch", { method: "POST" }),
                  "Compatibilidades recalculadas con tu perfil actual.",
                )
              }
            >
              <RefreshCw size={16} />
              Recalcular matching
            </button>
          </>
        }
      >
        Cada puntuación tiene una explicación. Cada requisito obligatorio
        cuenta.
      </PageHeader>
      <section className="panel search-panel">
        <form className="job-search-form" onSubmit={search}>
          <label className="search-field">
            <Search size={19} />
            <input
              aria-label="Qué oportunidad buscas"
              placeholder="Cargo, tecnología o palabra clave…"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              maxLength={200}
            />
          </label>
          <select
            aria-label="Fuente de vacantes"
            value={source}
            onChange={(event) => setSource(event.target.value)}
          >
            {sources.data?.length ? (
              sources.data
                .filter(
                  (item) =>
                    !Array.isArray(item.capabilities) &&
                    item.capabilities.search,
                )
                .map((item) => (
                  <option key={item.name} value={item.name}>
                    {item.label || item.name}
                  </option>
                ))
            ) : (
              <>
                <option value="remotive">Remotive · Fuente real</option>
                <option value="greenhouse">Greenhouse · Fuente real</option>
                <option value="demo">Demostración · Datos de prueba</option>
              </>
            )}
          </select>
          {source === "greenhouse" && (
            <input
              aria-label="Identificador del tablero Greenhouse"
              className="board-field"
              required
              value={board}
              onChange={(event) => setBoard(event.target.value)}
              placeholder="Tablero de empresa"
              pattern="[a-zA-Z0-9_-]+"
            />
          )}
          <button
            className="button button-primary"
            disabled={pending || searching}
          >
            {pending || searching ? <Spinner /> : <Search size={16} />}
            {searching ? "Buscando…" : "Buscar ofertas"}
          </button>
        </form>
        <div className="source-info">
          <Globe2 size={14} />
          <span>
            {sources.data?.find((item) => item.name === source)?.description ||
              (source === "demo"
                ? "Proveedor de pruebas: no representa vacantes reales ni envía datos a empresas."
                : "Búsqueda mediante la API pública de la fuente. Las postulaciones reales se completan en su portal.")}
          </span>
        </div>
        {task.error && (
          <ErrorPanel error={task.error} retry={() => void task.refetch()} />
        )}
        {searching && (
          <div role="status" className="task-status">
            <Spinner />
            Búsqueda en curso. Puedes seguir navegando mientras se procesan las
            ofertas.
          </div>
        )}
      </section>
      <section className="panel assisted-panel">
        <div>
          <h2>LinkedIn y Computrabajo, en tu espacio</h2>
          <p>
            Inicia sesión en tu navegador, elige una oferta y usa «Importar
            oferta» para analizar su texto aquí.
          </p>
        </div>
        <div className="assisted-portal-links">
          <a
            className="button button-secondary"
            href="https://www.linkedin.com/jobs/"
            target="_blank"
            rel="noopener noreferrer"
          >
            Abrir LinkedIn <ArrowUpRight size={14} />
          </a>
          <a
            className="button button-secondary"
            href="https://co.computrabajo.com/"
            target="_blank"
            rel="noopener noreferrer"
          >
            Abrir Computrabajo <ArrowUpRight size={14} />
          </a>
        </div>
      </section>
      <div className="list-toolbar">
        <div>
          <strong>{jobs.data?.length ?? "—"} oportunidades</strong>
          <span>en tu espacio</span>
        </div>
        <button
          className={`button button-secondary ${filtersOpen ? "selected-button" : ""}`}
          onClick={() => setFiltersOpen(!filtersOpen)}
          aria-expanded={filtersOpen}
        >
          <Filter size={16} />
          Filtros
          {Object.values(activeFilters).filter(Boolean).length > 0 && (
            <span className="filter-count">
              {Object.values(activeFilters).filter(Boolean).length}
            </span>
          )}
        </button>
      </div>
      {filtersOpen && (
        <form
          className="panel filter-panel"
          onSubmit={(event) => {
            event.preventDefault();
            setActiveFilters(filters);
          }}
        >
          <div className="form-grid">
            <label>
              Buscar en ofertas
              <input
                value={filters.q}
                onChange={(event) =>
                  setFilters({ ...filters, q: event.target.value })
                }
                placeholder="Título o descripción"
              />
            </label>
            <label>
              Compatibilidad mínima
              <input
                type="number"
                min={0}
                max={100}
                value={filters.min_score}
                onChange={(event) =>
                  setFilters({ ...filters, min_score: event.target.value })
                }
                placeholder="0 – 100"
              />
            </label>
            <label>
              Modalidad
              <select
                value={filters.work_mode}
                onChange={(event) =>
                  setFilters({ ...filters, work_mode: event.target.value })
                }
              >
                <option value="">Todas</option>
                <option value="remote">Remoto</option>
                <option value="hybrid">Híbrido</option>
                <option value="onsite">Presencial</option>
              </select>
            </label>
            <label>
              Empresa
              <input
                value={filters.company}
                onChange={(event) =>
                  setFilters({ ...filters, company: event.target.value })
                }
                placeholder="Nombre de la empresa"
              />
            </label>
            <label>
              Ubicación
              <input
                value={filters.location}
                onChange={(event) =>
                  setFilters({ ...filters, location: event.target.value })
                }
                placeholder="País o ciudad"
              />
            </label>
            <label>
              Tecnología
              <input
                value={filters.technology}
                onChange={(event) =>
                  setFilters({ ...filters, technology: event.target.value })
                }
                placeholder="Python, Java…"
              />
            </label>
            <label>
              Salario mínimo publicado
              <input
                type="number"
                min={0}
                value={filters.salary_min}
                onChange={(event) =>
                  setFilters({ ...filters, salary_min: event.target.value })
                }
                placeholder="Sin conversión de moneda"
              />
            </label>
            <label>
              Estado
              <select
                value={filters.status}
                onChange={(event) =>
                  setFilters({ ...filters, status: event.target.value })
                }
              >
                <option value="">Todos</option>
                {Object.entries(stateLabels).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Publicada desde
              <input
                type="date"
                value={filters.published_after}
                onChange={(event) =>
                  setFilters({
                    ...filters,
                    published_after: event.target.value,
                  })
                }
              />
            </label>
          </div>
          <div className="form-actions">
            <button
              type="button"
              className="text-button"
              onClick={() => {
                const empty = {
                  q: "",
                  min_score: "",
                  work_mode: "",
                  company: "",
                  location: "",
                  technology: "",
                  salary_min: "",
                  status: "",
                  published_after: "",
                };
                setFilters(empty);
                setActiveFilters(empty);
              }}
            >
              Limpiar filtros
            </button>
            <button className="button button-primary" type="submit">
              Aplicar filtros
            </button>
          </div>
        </form>
      )}
      {jobs.error ? (
        <ErrorPanel error={jobs.error} retry={() => void jobs.refetch()} />
      ) : jobs.isPending ? (
        <div className="loading-panel">
          <Spinner />
          Cargando oportunidades…
        </div>
      ) : !jobs.data?.length ? (
        <section className="panel">
          <Empty
            title="Hay un buen comienzo por delante"
            icon={BriefcaseBusiness}
          >
            Busca vacantes en una fuente autorizada o ajusta los filtros para
            ver más oportunidades. El proveedor de demostración permite probar
            el flujo completo.
          </Empty>
        </section>
      ) : (
        <div className="job-grid">
          {jobs.data.map((job) => (
            <article className="panel job-card" key={job.id}>
              <div className="job-card-top">
                <CompanyMark company={job.company} />
                <div>
                  <span className="job-company">{job.company}</span>
                  <span className="job-date">
                    {formatDate(job.published_at)}
                  </span>
                </div>
                <span
                  className={`score-ring ${(job.match?.score ?? 0) >= 80 ? "score-high" : ""}`}
                >
                  <strong>
                    {job.match ? Math.round(job.match.score) : "—"}
                  </strong>
                  <small>/100</small>
                </span>
              </div>
              <button
                className="job-title-button"
                onClick={() => setSelected(job)}
              >
                <h2>{job.title}</h2>
              </button>
              <div className="job-meta">
                <span>
                  <MapPin size={14} />
                  {job.location || "Ubicación por confirmar"}
                </span>
                <span>
                  <Globe2 size={14} />
                  {modeLabels[job.work_mode] || job.work_mode}
                </span>
              </div>
              <div className="skill-tags">
                {job.skills.slice(0, 5).map((skill) => (
                  <Badge key={skill}>{skill}</Badge>
                ))}
                {job.skills.length > 5 && (
                  <Badge>+{job.skills.length - 5}</Badge>
                )}
              </div>
              <p className="job-salary">{money(job)}</p>
              {job.ingestion_method === "assisted" && (
                <Badge tone="blue">Importación asistida</Badge>
              )}
              <div className="job-decision">
                {job.match?.eligible ? (
                  <>
                    <CheckCircle2 size={15} />
                    <span>Requisitos verificados</span>
                  </>
                ) : (
                  <>
                    <CircleAlert size={15} />
                    <span>
                      {job.match
                        ? "Requiere revisión"
                        : "Pendiente de análisis"}
                    </span>
                  </>
                )}
              </div>
              <div className="job-card-footer">
                <a
                  href={safeExternalUrl(job.url)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="source-link"
                >
                  {job.source === "demo"
                    ? "Datos de prueba"
                    : `Fuente: ${job.source}`}
                  <ArrowUpRight size={12} />
                </a>
                <button
                  className="text-button"
                  onClick={() => setSelected(job)}
                >
                  Ver oportunidad <ArrowRight size={14} />
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
      {importOpen && (
        <AssistedImportDialog
          initialJob={importDraft || undefined}
          notify={notify}
          onClose={() => setImportOpen(false)}
          onImported={(job) => {
            setImportOpen(false);
            setSelected(job);
          }}
        />
      )}
      {selected && (
        <Modal
          title={selected.title}
          subtitle={selected.company}
          onClose={() => setSelected(null)}
        >
          <div className="detail-meta">
            {selected.ingestion_method === "assisted" && (
              <Badge tone="blue">Texto aportado por ti</Badge>
            )}
            <Badge tone={selected.source === "demo" ? "orange" : "teal"}>
              {selected.source === "demo" ? "Demostración" : selected.source}
            </Badge>
            <span>
              <MapPin size={14} />
              {selected.location}
            </span>
            <span>{money(selected)}</span>
          </div>
          {selected.match && (
            <section className="match-details">
              <div className="match-detail-score">
                <strong>
                  {Math.round(selected.match.score)}
                  <small>/100</small>
                </strong>
                <div>
                  <h3>Compatibilidad con tu perfil</h3>
                  <p>{selected.match.decision}</p>
                </div>
              </div>
              <div className="breakdown">
                {Object.entries(selected.match.breakdown).map(
                  ([criterion, value]) => (
                    <div key={criterion}>
                      <span>
                        {(
                          {
                            technical: "Habilidades técnicas",
                            experience: "Experiencia",
                            seniority: "Seniority",
                            preferences: "Preferencias",
                            salary: "Salario",
                            languages: "Idiomas y requisitos",
                            additional: "Requisitos adicionales",
                          } as Record<string, string>
                        )[criterion] || criterion}
                      </span>
                      <div>
                        <i
                          style={{
                            width: `${Math.max(0, Math.min(100, value))}%`,
                          }}
                        />
                      </div>
                      <strong>{Number(value).toFixed(0)}</strong>
                    </div>
                  ),
                )}
              </div>
              <div className="match-columns">
                <div>
                  <h4>
                    <CheckCircle2 size={16} />
                    Coincidencias
                  </h4>
                  {selected.match.matches.length ? (
                    selected.match.matches.map((match, index) => (
                      <p key={index}>{match}</p>
                    ))
                  ) : (
                    <p className="muted">Sin coincidencias verificadas.</p>
                  )}
                </div>
                <div>
                  <h4>
                    <CircleAlert size={16} />
                    Brechas por revisar
                  </h4>
                  {[...selected.match.gaps, ...selected.match.blockers]
                    .length ? (
                    [...selected.match.gaps, ...selected.match.blockers].map(
                      (gap, index) => <p key={index}>{gap}</p>,
                    )
                  ) : (
                    <p className="muted">Sin brechas detectadas.</p>
                  )}
                </div>
              </div>
            </section>
          )}
          <h3 className="detail-heading">Sobre la oportunidad</h3>
          <div className="job-description">{selected.description}</div>
          {selected.mandatory_requirements.length > 0 && (
            <>
              <h3 className="detail-heading">Requisitos obligatorios</h3>
              <ul className="requirements-list">
                {selected.mandatory_requirements.map((requirement, index) => (
                  <li key={index}>{requirement}</li>
                ))}
              </ul>
            </>
          )}
          <div className="modal-actions">
            {selected.ingestion_method === "assisted" &&
              !["SUBMITTED", "CONFIRMED", "WITHDRAWN", "SKIPPED"].includes(
                selected.application_state || "",
              ) && (
                <button
                  className="button button-secondary"
                  onClick={() => {
                    setImportDraft(selected);
                    setSelected(null);
                    setImportOpen(true);
                  }}
                >
                  <FileText size={15} />
                  Completar datos
                </button>
              )}
            <a
              className="button button-secondary"
              href={safeExternalUrl(selected.url)}
              target="_blank"
              rel="noopener noreferrer"
            >
              Abrir en {selected.source}
              <ArrowUpRight size={15} />
            </a>
            <button
              className="button button-primary"
              disabled={
                pending ||
                (!selected.match?.eligible &&
                  !selected.match?.requires_human_review)
              }
              onClick={() => prepare(selected)}
            >
              {pending ? <Spinner /> : <FileText size={16} />}Preparar
              candidatura
            </button>
          </div>
          {!selected.match?.eligible && (
            <p className="helper-text">
              La preparación requiere un perfil revisado y una oferta elegible
              según tus reglas.
            </p>
          )}
        </Modal>
      )}
    </>
  );
}
