"use client";

import { useQuery } from "@tanstack/react-query";
import {
  ArrowDownToLine,
  ArrowRight,
  ArrowUpRight,
  BriefcaseBusiness,
  Check,
  ChevronRight,
  Clock3,
  FileCheck2,
  Search,
  Send,
  ShieldCheck,
  Sparkles,
  Target,
  UserRound,
} from "lucide-react";
import { api, downloadReport } from "@/lib/api";
import { type Dashboard, type Job, type ProfileRecord } from "@/types";
import {
  formatDate,
  useAction,
  Badge,
  Empty,
  ErrorPanel,
  PageHeader,
  CompanyMark,
  type Section,
  type Notify,
  modeLabels,
} from "@/components/shared";

export default function Overview({
  data,
  error,
  loading,
  retry,
  go,
  notify,
  name,
}: {
  data?: Dashboard;
  error: unknown;
  loading: boolean;
  retry: () => void;
  go: (section: Section) => void;
  notify: Notify;
  name?: string;
}) {
  const { run, pending } = useAction(notify);
  const profile = useQuery({
    queryKey: ["profile"],
    queryFn: () => api<ProfileRecord | null>("/profile"),
  });
  const jobs = useQuery({
    queryKey: ["jobs", "overview"],
    queryFn: () => api<Job[]>("/jobs?min_score=0"),
  });
  const topJobs = [...(jobs.data || [])]
    .sort((a, b) => (b.match?.score || 0) - (a.match?.score || 0))
    .slice(0, 3);
  return (
    <>
      <PageHeader
        eyebrow="VISTA GENERAL"
        title={`Tu próximo paso empieza aquí${name ? `, ${name.split(" ")[0]}` : ""}.`}
        actions={
          <button
            className="button button-secondary"
            disabled={pending}
            onClick={() => run(downloadReport, "Reporte descargado.")}
          >
            <ArrowDownToLine size={16} />
            Exportar reporte
          </button>
        }
      >
        Una búsqueda con propósito. Toda tu actividad, en un solo lugar.
      </PageHeader>
      {error ? <ErrorPanel error={error} retry={retry} /> : null}
      <section className="hero-card">
        <div className="hero-content">
          <Badge tone="light">
            <span className="small-dot" />
            TU CARRERA, CON DIRECCIÓN
          </Badge>
          <h2>
            Las buenas oportunidades
            <br />
            empiezan con un buen perfil.
          </h2>
          <p>
            Tu experiencia y tus preferencias nos ayudan a encontrar
            <br className="desktop-break" />
            vacantes que tengan sentido para ti.
          </p>
          <button
            className="button button-white"
            onClick={() => go(profile.data?.reviewed ? "jobs" : "profile")}
          >
            {profile.data?.reviewed
              ? "Explorar oportunidades"
              : "Completar mi perfil"}
            <ArrowUpRight size={17} />
          </button>
        </div>
        <div className="hero-art" aria-hidden="true">
          <div className="orb orb-one" />
          <div className="orb orb-two" />
          <div className="orbit orbit-one" />
          <div className="orbit orbit-two" />
          <div className="art-card art-card-back">
            <Target size={22} />
            <div className="art-line" />
            <div className="art-line short" />
          </div>
          <div className="art-card art-card-front">
            <div className="art-icon">
              <BriefcaseBusiness size={28} />
            </div>
            <div>
              <div className="art-line" />
              <div className="art-line short" />
            </div>
            <span className="art-check">
              <Check size={15} />
            </span>
          </div>
          <span className="floating-spark">
            <Sparkles size={27} />
          </span>
          <span className="art-caption">
            Tu talento + la oportunidad correcta
          </span>
        </div>
      </section>
      <section className="metric-grid" aria-label="Estadísticas de tu búsqueda">
        {[
          {
            label: "Ofertas encontradas",
            value: data?.jobs,
            icon: Search,
            note: "En tus fuentes de búsqueda",
            color: "blue",
          },
          {
            label: "Oportunidades elegibles",
            value: data?.eligible_jobs,
            icon: Target,
            note: "Cumplen los requisitos",
            color: "teal",
          },
          {
            label: "Por revisar",
            value: data?.pending_approval,
            icon: FileCheck2,
            note: "Esperan tu aprobación",
            color: "orange",
          },
          {
            label: "Envíos registrados",
            value: data?.submitted,
            icon: Send,
            note: `${data?.real_submitted ?? "—"} reales · ${data?.demo_submitted ?? "—"} de prueba`,
            color: "purple",
          },
        ].map(({ label, value, icon: Icon, note, color }) => (
          <div key={label} className="metric-card">
            <div className="metric-top">
              <span>{label}</span>
              <span className={`metric-icon ${color}`}>
                <Icon size={18} />
              </span>
            </div>
            <div className="metric-value">
              {loading ? (
                <span className="skeleton skeleton-value" />
              ) : (
                (value ?? "—")
              )}
            </div>
            <p>{note}</p>
          </div>
        ))}
      </section>
      <div className="overview-grid">
        <section className="panel opportunities-preview">
          <div className="panel-heading">
            <div>
              <h2>
                Oportunidades para ti{" "}
                <span className="tiny-label">TU SELECCIÓN</span>
              </h2>
              <p>Ordenadas por compatibilidad con tu perfil.</p>
            </div>
            <button className="text-button" onClick={() => go("jobs")}>
              Ver todas <ArrowRight size={15} />
            </button>
          </div>
          {topJobs.length ? (
            <div className="preview-jobs">
              {topJobs.map((job) => (
                <button
                  className="preview-job"
                  key={job.id}
                  onClick={() => go("jobs")}
                >
                  <CompanyMark company={job.company} />
                  <div className="preview-job-text">
                    <strong>{job.title}</strong>
                    <span>
                      {job.company} <i>·</i>{" "}
                      {modeLabels[job.work_mode] || job.work_mode}
                    </span>
                  </div>
                  <div
                    className={`score-pill ${(job.match?.score ?? 0) >= 80 ? "high" : ""}`}
                  >
                    {job.match ? `${Math.round(job.match.score)}%` : "—"}
                    <small>match</small>
                  </div>
                  <ChevronRight size={16} />
                </button>
              ))}
            </div>
          ) : (
            <Empty
              title="Tu próxima oportunidad está por llegar"
              action={
                <button
                  className="button button-secondary"
                  onClick={() => go("jobs")}
                >
                  <Search size={16} />
                  Buscar vacantes
                </button>
              }
            >
              Carga y revisa tu perfil; luego explora ofertas de las fuentes
              autorizadas.
            </Empty>
          )}
        </section>
        <section className="panel profile-progress">
          <div className="panel-heading">
            <h2>Tu punto de partida</h2>
            <span className="round-icon">
              <UserRound size={17} />
            </span>
          </div>
          <div className="progress-track">
            <span
              style={{
                width: profile.data?.reviewed
                  ? "100%"
                  : profile.data
                    ? "50%"
                    : "0%",
              }}
            />
          </div>
          <div className="progress-caption">
            <strong>
              {profile.data?.reviewed
                ? "Listo para explorar"
                : profile.data
                  ? "Un paso más"
                  : "Construye tu perfil"}
            </strong>
            <span>
              {profile.data?.reviewed
                ? "2 de 2"
                : profile.data
                  ? "1 de 2"
                  : "0 de 2"}
            </span>
          </div>
          <div className="setup-step">
            <span className={`step-check ${profile.data ? "done" : ""}`}>
              {profile.data ? <Check size={13} /> : "1"}
            </span>
            <div>
              <strong>Sube tu hoja de vida</strong>
              <p>PDF, DOCX o TXT</p>
            </div>
          </div>
          <div className="setup-step">
            <span
              className={`step-check ${profile.data?.reviewed ? "done" : ""}`}
            >
              {profile.data?.reviewed ? <Check size={13} /> : "2"}
            </span>
            <div>
              <strong>Revisa los datos extraídos</strong>
              <p>Confirma lo que compartiremos</p>
            </div>
          </div>
          <button
            className="button button-secondary full-width"
            onClick={() => go("profile")}
          >
            Ver mi perfil <ArrowRight size={15} />
          </button>
          <div className="privacy-note">
            <ShieldCheck size={15} />
            <span>La información no confirmada requiere tu revisión.</span>
          </div>
        </section>
      </div>
      <div className="overview-grid lower-grid">
        <section className="panel activity-panel">
          <div className="panel-heading">
            <div>
              <h2>Actividad reciente</h2>
              <p>El registro de cada paso.</p>
            </div>
            <Clock3 size={18} className="muted" />
          </div>
          {data?.recent_events?.length ? (
            <div className="event-list">
              {data.recent_events.slice(0, 6).map((event) => (
                <div className="event-row" key={event.id}>
                  <span className="event-dot" />
                  <div>
                    <p>{event.message}</p>
                    <small>{event.kind}</small>
                  </div>
                  <time>{formatDate(event.created_at)}</time>
                </div>
              ))}
            </div>
          ) : (
            <div className="quiet-empty">
              Cuando comiences, verás aquí tus búsquedas y candidaturas.
            </div>
          )}
        </section>
        <section className="panel insights-panel">
          <div className="panel-heading">
            <h2>Tu brújula profesional</h2>
            <Sparkles size={18} className="teal-text" />
          </div>
          <div className="insight-line">
            <span>Compatibilidad promedio</span>
            <strong>
              {data ? `${Math.round(data.average_score)} / 100` : "—"}
            </strong>
          </div>
          <div className="insight-line">
            <span>Costo aproximado de IA</span>
            <strong>
              {data?.ai_cost_usd != null
                ? `USD ${Number(data.ai_cost_usd).toFixed(4)}`
                : "Sin medici\u00f3n"}
            </strong>
          </div>
          {data?.ai_cost_note && (
            <p className="cost-note">{data.ai_cost_note}</p>
          )}
          <div className="insight-divider" />
          <h3>Habilidades por fortalecer</h3>
          {data?.skill_gaps?.length ? (
            <div className="gap-list">
              {data.skill_gaps.slice(0, 4).map((gap) => (
                <div key={gap.skill}>
                  <span>{gap.skill}</span>
                  <small>
                    {gap.count} oferta{gap.count === 1 ? "" : "s"}
                  </small>
                </div>
              ))}
            </div>
          ) : (
            <p className="muted small-text">
              Analiza ofertas para descubrir qué habilidades pueden abrirte más
              puertas.
            </p>
          )}
        </section>
      </div>
    </>
  );
}
