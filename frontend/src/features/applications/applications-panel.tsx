"use client";

import { useQuery } from "@tanstack/react-query";
import {
  ArrowDownToLine,
  ArrowRight,
  ArrowUpRight,
  BadgeCheck,
  Check,
  CheckCheck,
  CircleAlert,
  Clock3,
  Copy,
  FileCheck2,
  FileText,
  RefreshCw,
  Send,
  XCircle,
} from "lucide-react";
import { useState } from "react";
import { api, downloadReport, downloadText, safeExternalUrl } from "@/lib/api";
import { type Application } from "@/types";
import {
  formatDate,
  useAction,
  Spinner,
  Empty,
  ErrorPanel,
  PageHeader,
  CompanyMark,
  Modal,
  StateBadge,
  type Notify,
  stateLabels,
} from "@/components/shared";

export default function ApplicationsPanel({ notify }: { notify: Notify }) {
  const applications = useQuery({
    queryKey: ["applications"],
    queryFn: () => api<Application[]>("/applications"),
  });
  const [filter, setFilter] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [manualConfirm, setManualConfirm] = useState(false);
  const { run, pending } = useAction(notify);
  const selected = applications.data?.find(
    (application) => application.id === selectedId,
  );
  const filtered = (applications.data || []).filter(
    (application) => !filter || application.state === filter,
  );
  const action = (
    id: string,
    endpoint: string,
    message: string,
    body?: unknown,
  ) =>
    run(
      () =>
        api(`/applications/${id}/${endpoint}`, {
          method: "POST",
          ...(body ? { body: JSON.stringify(body) } : {}),
        }),
      message,
    );
  return (
    <>
      <PageHeader
        eyebrow="CANDIDATURAS"
        title="Cada candidatura cuenta una historia."
        actions={
          <button
            className="button button-secondary"
            disabled={pending}
            onClick={() => run(downloadReport, "Reporte descargado.")}
          >
            <ArrowDownToLine size={16} />
            Descargar historial
          </button>
        }
      >
        Revisa lo que vas a compartir y acompaña el avance de cada postulación.
      </PageHeader>
      <div className="application-summary">
        <div>
          <span className="application-stat-icon">
            <FileText size={20} />
          </span>
          <div>
            <strong>{applications.data?.length ?? "—"}</strong>
            <span>Candidaturas registradas</span>
          </div>
        </div>
        <div>
          <span className="application-stat-icon orange">
            <Clock3 size={20} />
          </span>
          <div>
            <strong>
              {applications.data?.filter(
                (item) => item.state === "PENDING_APPROVAL",
              ).length ?? "—"}
            </strong>
            <span>Esperan tu aprobación</span>
          </div>
        </div>
        <div>
          <span className="application-stat-icon teal">
            <CheckCheck size={20} />
          </span>
          <div>
            <strong>
              {applications.data?.filter((item) => item.state === "CONFIRMED")
                .length ?? "—"}
            </strong>
            <span>Confirmadas</span>
          </div>
        </div>
      </div>
      <section className="panel">
        <div className="panel-heading applications-heading">
          <h2>Tu historial</h2>
          <select
            aria-label="Filtrar candidaturas por estado"
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
          >
            <option value="">Todos los estados</option>
            {Object.entries(stateLabels).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>
        {applications.error ? (
          <ErrorPanel
            error={applications.error}
            retry={() => void applications.refetch()}
          />
        ) : applications.isPending ? (
          <div className="loading-panel">
            <Spinner />
            Cargando candidaturas…
          </div>
        ) : !filtered.length ? (
          <Empty title="Tu historia está por empezar" icon={FileText}>
            Prepara una candidatura desde una oferta elegible. Aquí podrás
            revisar su contenido, aprobarla y consultar cada cambio de estado.
          </Empty>
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>OPORTUNIDAD</th>
                  <th>ESTADO</th>
                  <th>FUENTE</th>
                  <th>ACTUALIZADA</th>
                  <th>
                    <span className="sr-only">Acciones</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((application) => (
                  <tr key={application.id}>
                    <td>
                      <div className="table-company">
                        <CompanyMark company={application.company} />
                        <div>
                          <strong>{application.job_title}</strong>
                          <small>{application.company}</small>
                        </div>
                      </div>
                    </td>
                    <td>
                      <StateBadge state={application.state} />
                    </td>
                    <td>
                      <span className="source-cell">
                        {application.source}
                        {application.source === "demo" && <small>Prueba</small>}
                      </span>
                    </td>
                    <td className="muted">
                      {formatDate(application.updated_at)}
                    </td>
                    <td>
                      <button
                        className="text-button"
                        onClick={() => {
                          setSelectedId(application.id);
                          setManualConfirm(false);
                        }}
                      >
                        Revisar <ArrowRight size={14} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
      {selected && (
        <Modal
          title={selected.job_title}
          subtitle={selected.company}
          onClose={() => setSelectedId(null)}
        >
          <div className="application-detail-status">
            <StateBadge state={selected.state} />
            <span>
              {selected.source === "demo"
                ? "Proveedor de pruebas · No se envían datos a empresas"
                : `Fuente: ${selected.source}`}
            </span>
          </div>
          <h3 className="detail-heading">Resumen profesional adaptado</h3>
          <div className="document-preview">
            {selected.packet.summary || "Sin resumen disponible."}
          </div>
          <h3 className="detail-heading">Carta de presentación</h3>
          <div className="document-preview letter-preview">
            {selected.packet.cover_letter || "Sin carta disponible."}
          </div>
          {selected.packet.cover_letter && (
            <button
              className="button button-secondary"
              style={{ marginTop: 16 }}
              disabled={pending}
              onClick={() =>
                run(
                  () =>
                    navigator.clipboard.writeText(
                      selected.packet.cover_letter || "",
                    ),
                  "Carta copiada al portapapeles.",
                )
              }
            >
              <Copy size={15} />
              Copiar carta
            </button>
          )}
          {selected.packet.cv_text && (
            <button
              className="button button-secondary"
              style={{ marginTop: 16 }}
              onClick={() =>
                downloadText(
                  `candidatura-${selected.id}.txt`,
                  selected.packet.cv_text || "",
                )
              }
            >
              <ArrowDownToLine size={15} />
              Descargar CV adaptado · TXT
            </button>
          )}
          {selected.packet.questions &&
            Object.keys(selected.packet.questions).length > 0 && (
              <>
                <h3 className="detail-heading">Respuestas de selección</h3>
                <pre className="json-preview">
                  {JSON.stringify(selected.packet.questions, null, 2)}
                </pre>
              </>
            )}
          {(selected.packet.pending_questions?.length || 0) > 0 && (
            <div className="warning-box">
              <CircleAlert size={18} />
              <div>
                <strong>Hay respuestas por validar</strong>
                <pre>
                  {JSON.stringify(selected.packet.pending_questions, null, 2)}
                </pre>
              </div>
            </div>
          )}
          {selected.result_reference && (
            <div className="reference-box">
              <BadgeCheck size={18} />
              <div>
                <span>Referencia del resultado</span>
                <code>{selected.result_reference}</code>
              </div>
            </div>
          )}
          {selected.events?.length ? (
            <>
              <h3 className="detail-heading">Trazabilidad</h3>
              <div className="event-list">
                {selected.events.map((event, index) => (
                  <div className="event-row" key={index}>
                    <span className="event-dot" />
                    <div>
                      <p>{event.message}</p>
                      <small>{event.kind}</small>
                    </div>
                    <time>{formatDate(event.created_at)}</time>
                  </div>
                ))}
              </div>
            </>
          ) : null}
          <div className="modal-actions">
            {!["SUBMITTED", "CONFIRMED", "WITHDRAWN", "SKIPPED"].includes(
              selected.state,
            ) && (
              <button
                className="button button-secondary"
                disabled={pending}
                onClick={() =>
                  action(
                    selected.id,
                    "regenerate",
                    "Candidatura actualizada con el perfil y contexto vigentes.",
                  )
                }
              >
                <RefreshCw size={15} />
                Regenerar borrador
              </button>
            )}
            {["PREPARED", "PENDING_APPROVAL", "NEEDS_INFORMATION"].includes(
              selected.state,
            ) && (
              <>
                <button
                  className="button button-secondary"
                  disabled={pending}
                  onClick={() =>
                    action(selected.id, "reject", "Candidatura descartada.")
                  }
                >
                  <XCircle size={16} />
                  Descartar
                </button>
                <button
                  className="button button-primary"
                  disabled={
                    pending ||
                    selected.approved ||
                    (selected.packet.pending_questions?.length || 0) > 0
                  }
                  onClick={() =>
                    action(selected.id, "approve", "Candidatura aprobada.")
                  }
                >
                  <Check size={17} />
                  {selected.approved ? "Aprobada" : "Aprobar contenido"}
                </button>
              </>
            )}
            {selected.approved &&
              ["PREPARED", "PENDING_APPROVAL", "RETRY_PENDING"].includes(
                selected.state,
              ) &&
              selected.source === "demo" && (
                <button
                  className="button button-primary"
                  disabled={pending}
                  onClick={() =>
                    action(
                      selected.id,
                      "submit",
                      "Envío de prueba ejecutado. Revisa el estado y la referencia.",
                    )
                  }
                >
                  <Send size={16} />
                  Enviar al proveedor de pruebas
                </button>
              )}
          </div>
          {selected.source !== "demo" &&
            ![
              "CONFIRMED",
              "WITHDRAWN",
              "SKIPPED",
              "REJECTED_BY_RULES",
            ].includes(selected.state) && (
              <div className="manual-confirm-panel">
                <h3>Registro de postulación manual</h3>
                <p>
                  Completa el proceso en el portal de la oferta y registra aquí
                  el resultado.
                </p>
                {selected.url && (
                  <a
                    className="button button-secondary"
                    href={safeExternalUrl(selected.url)}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    Abrir oferta original <ArrowUpRight size={15} />
                  </a>
                )}
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={manualConfirm}
                    onChange={(event) => setManualConfirm(event.target.checked)}
                  />
                  <span>
                    La plataforma confirmó que recibió mi candidatura.
                  </span>
                </label>
                <button
                  className="button button-secondary"
                  disabled={pending || !selected.approved}
                  onClick={() =>
                    action(
                      selected.id,
                      "manual-confirm",
                      manualConfirm
                        ? "Confirmación manual registrada."
                        : "Envío manual registrado.",
                      { confirmed: manualConfirm },
                    )
                  }
                >
                  <FileCheck2 size={16} />
                  {manualConfirm
                    ? "Registrar confirmación"
                    : "Registrar formulario enviado"}
                </button>
              </div>
            )}
        </Modal>
      )}
    </>
  );
}
