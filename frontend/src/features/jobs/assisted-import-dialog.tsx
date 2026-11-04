"use client";

import { useState, type FormEvent } from "react";
import { ClipboardPaste, Save } from "lucide-react";
import { api } from "@/lib/api";
import { type Job } from "@/types";
import { Modal, Spinner, useAction, type Notify } from "@/components/shared";

export default function AssistedImportDialog({
  onClose,
  onImported,
  notify,
  initialJob,
}: {
  onClose: () => void;
  onImported: (job: Job) => void;
  notify: Notify;
  initialJob?: Job;
}) {
  const [draft, setDraft] = useState({
    source: initialJob?.source || "linkedin",
    url: initialJob?.url || "",
    title: initialJob?.title || "",
    company: initialJob?.company || "",
    description: initialJob?.description || "",
    location: initialJob?.location || "",
    work_mode: initialJob?.work_mode || "unknown",
    salary_min:
      initialJob?.salary_min == null ? "" : String(initialJob.salary_min),
    salary_max:
      initialJob?.salary_max == null ? "" : String(initialJob.salary_max),
    currency: initialJob?.currency || "COP",
    salary_period:
      initialJob?.salary_period && initialJob.salary_period !== "unknown"
        ? initialJob.salary_period
        : "month",
    minimum_years:
      initialJob?.minimum_years == null ? "" : String(initialJob.minimum_years),
    contract_type: initialJob?.contract_type || "",
    mandatory_requirements: initialJob?.mandatory_requirements.join("\n") || "",
  });
  const { pending, run } = useAction(notify);
  const update = (field: keyof typeof draft, value: string) =>
    setDraft((previous) => ({ ...previous, [field]: value }));
  const submit = (event: FormEvent) => {
    event.preventDefault();
    const hasSalary = draft.salary_min !== "" || draft.salary_max !== "";
    void run(async () => {
      const result = await api<{
        job: Job;
        duplicate: boolean;
        message: string;
      }>(initialJob ? `/jobs/${initialJob.id}/import` : "/jobs/import", {
        method: initialJob ? "PUT" : "POST",
        body: JSON.stringify({
          ...draft,
          salary_min: draft.salary_min === "" ? null : Number(draft.salary_min),
          salary_max: draft.salary_max === "" ? null : Number(draft.salary_max),
          minimum_years:
            draft.minimum_years === "" ? null : Number(draft.minimum_years),
          currency: hasSalary ? draft.currency.trim().toUpperCase() : null,
          salary_period: hasSalary ? draft.salary_period : "unknown",
          mandatory_requirements: draft.mandatory_requirements
            .split("\n")
            .map((line) => line.trim())
            .filter(Boolean),
        }),
      });
      notify({ kind: "success", message: result.message });
      onImported(result.job);
    });
  };
  return (
    <Modal
      title={initialJob ? "Completar oferta importada" : "Importar una oferta"}
      subtitle="LINKEDIN · COMPUTRABAJO · OTROS PORTALES"
      onClose={onClose}
    >
      <p className="helper-text assisted-import-intro">
        Abre la oferta en tu navegador y pega aquí su contenido o el texto de la
        alerta que recibiste. Los datos se guardan en tu espacio. La app no abre
        el enlace ni accede a tus cuentas.
      </p>
      <form className="assisted-import-form" onSubmit={submit}>
        <fieldset disabled={pending}>
          <div className="form-grid">
            <label>
              Portal de la oferta
              <select
                aria-label="Portal de la oferta"
                disabled={Boolean(initialJob)}
                value={draft.source}
                onChange={(event) => update("source", event.target.value)}
              >
                <option value="linkedin">LinkedIn</option>
                <option value="computrabajo">Computrabajo</option>
                <option value="manual">Otro portal</option>
              </select>
            </label>
            <label>
              Enlace original de la oferta
              <input
                type="url"
                readOnly={Boolean(initialJob)}
                required
                maxLength={3000}
                value={draft.url}
                onChange={(event) => update("url", event.target.value)}
                placeholder="https://…"
              />
            </label>
            <label>
              Cargo de la oferta
              <input
                required
                minLength={2}
                maxLength={500}
                value={draft.title}
                onChange={(event) => update("title", event.target.value)}
                placeholder="Ej. Desarrollador Java Senior"
              />
            </label>
            <label>
              Empresa de la oferta
              <input
                required
                minLength={2}
                maxLength={300}
                value={draft.company}
                onChange={(event) => update("company", event.target.value)}
                placeholder="Nombre tal como aparece publicado"
              />
            </label>
          </div>
          <label className="wide-label">
            Texto de la oferta o alerta
            <textarea
              aria-label="Texto de la oferta o alerta"
              required
              minLength={20}
              maxLength={100000}
              rows={8}
              value={draft.description}
              onChange={(event) => update("description", event.target.value)}
              placeholder="Pega la descripción, responsabilidades, requisitos y condiciones publicadas…"
            />
          </label>
          <div className="form-grid">
            <label>
              Ubicación publicada
              <input
                maxLength={500}
                value={draft.location}
                onChange={(event) => update("location", event.target.value)}
                placeholder="Déjalo vacío si no se publica"
              />
            </label>
            <label>
              Modalidad publicada
              <select
                aria-label="Modalidad publicada"
                value={draft.work_mode}
                onChange={(event) => update("work_mode", event.target.value)}
              >
                <option value="unknown">Sin especificar</option>
                <option value="remote">Remoto</option>
                <option value="hybrid">Híbrido</option>
                <option value="onsite">Presencial</option>
              </select>
            </label>
          </div>
          <details className="assisted-extra-fields">
            <summary>Salario y requisitos publicados · opcional</summary>
            <p className="helper-text">
              Completa sólo lo que publique la oferta. Un salario ausente
              permanece por confirmar. Para un salario fijo, repite el importe
              en ambos campos.
            </p>
            <div className="form-grid">
              <label>
                Salario publicado desde
                <input
                  type="number"
                  min={0}
                  step="any"
                  value={draft.salary_min}
                  onChange={(event) => update("salary_min", event.target.value)}
                  placeholder="Sin especificar"
                />
              </label>
              <label>
                Salario publicado hasta
                <input
                  type="number"
                  min={0}
                  step="any"
                  value={draft.salary_max}
                  onChange={(event) => update("salary_max", event.target.value)}
                  placeholder="Sin especificar"
                />
              </label>
              <label>
                Moneda publicada
                <input
                  value={draft.currency}
                  maxLength={3}
                  pattern="[A-Za-z]{3}"
                  onChange={(event) => update("currency", event.target.value)}
                  placeholder="COP, USD, EUR…"
                />
              </label>
              <label>
                Periodicidad publicada
                <select
                  aria-label="Periodicidad publicada"
                  value={draft.salary_period}
                  onChange={(event) =>
                    update("salary_period", event.target.value)
                  }
                >
                  <option value="month">Mensual</option>
                  <option value="year">Anual</option>
                  <option value="hour">Por hora</option>
                </select>
              </label>
              <label>
                Experiencia mínima publicada · años
                <input
                  type="number"
                  min={0}
                  max={80}
                  step={0.5}
                  value={draft.minimum_years}
                  onChange={(event) =>
                    update("minimum_years", event.target.value)
                  }
                  placeholder="Sin especificar"
                />
              </label>
              <label>
                Tipo de contrato publicado
                <select
                  aria-label="Tipo de contrato publicado"
                  value={draft.contract_type}
                  onChange={(event) =>
                    update("contract_type", event.target.value)
                  }
                >
                  <option value="">Sin especificar</option>
                  <option value="indefinido">Término indefinido</option>
                  <option value="termino fijo">Término fijo</option>
                  <option value="prestacion de servicios">
                    Prestación de servicios
                  </option>
                  <option value="freelance">Freelance</option>
                </select>
              </label>
            </div>
            <label className="wide-label">
              Requisitos obligatorios · uno por línea
              <textarea
                aria-label="Requisitos obligatorios · uno por línea"
                rows={4}
                maxLength={50000}
                value={draft.mandatory_requirements}
                onChange={(event) =>
                  update("mandatory_requirements", event.target.value)
                }
                placeholder="Sólo requisitos explícitamente obligatorios…"
              />
            </label>
          </details>
        </fieldset>
        <div className="modal-actions">
          <span className="assisted-local-note">
            <ClipboardPaste size={15} />
            Importación por texto, sin credenciales
          </span>
          <button
            type="button"
            className="button button-secondary"
            disabled={pending}
            onClick={onClose}
          >
            Cancelar
          </button>
          <button
            type="submit"
            className="button button-primary"
            disabled={pending}
          >
            {pending ? <Spinner /> : <Save size={16} />}
            {initialJob ? "Guardar cambios y analizar" : "Guardar y analizar"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
