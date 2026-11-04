"use client";

import { useQueryClient } from "@tanstack/react-query";
import {
  BriefcaseBusiness,
  CircleAlert,
  LayoutDashboard,
  Loader2,
  Search,
  SlidersHorizontal,
  UserRound,
  X,
} from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { type Job } from "@/types";

export type Section =
  "dashboard" | "jobs" | "applications" | "profile" | "context";
export type Notice = { kind: "success" | "error"; message: string };
export type Notify = (notice: Notice) => void;

export const sections: { id: Section; label: string; icon: typeof Search }[] = [
  { id: "dashboard", label: "Vista general", icon: LayoutDashboard },
  { id: "jobs", label: "Oportunidades", icon: Search },
  { id: "applications", label: "Candidaturas", icon: BriefcaseBusiness },
  { id: "profile", label: "Mi perfil", icon: UserRound },
  { id: "context", label: "Contexto y reglas", icon: SlidersHorizontal },
];

export const stateLabels: Record<string, string> = {
  DISCOVERED: "Descubierta",
  ANALYZED: "Analizada",
  ELIGIBLE: "Elegible",
  PREPARED: "Preparada",
  PENDING_APPROVAL: "Por aprobar",
  SUBMITTED: "Enviada",
  CONFIRMED: "Confirmada",
  REJECTED_BY_RULES: "Descartada por reglas",
  NEEDS_INFORMATION: "Falta información",
  FAILED: "Error",
  RETRY_PENDING: "Reintento pendiente",
  SKIPPED: "Descartada",
  WITHDRAWN: "Retirada",
};

export const modeLabels: Record<string, string> = {
  remote: "Remoto",
  hybrid: "Híbrido",
  onsite: "Presencial",
  on_site: "Presencial",
  unknown: "Por confirmar",
};
export const isCompleteTask = (status: string) =>
  [
    "completed",
    "success",
    "succeeded",
    "done",
    "failed",
    "failure",
    "cancelled",
  ].includes(status.toLowerCase());

export function formatDate(value?: string | null) {
  if (!value) return "Sin fecha";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Sin fecha";
  return new Intl.DateTimeFormat("es-CO", {
    day: "numeric",
    month: "short",
    timeZone: "America/Bogota",
  }).format(date);
}

export function money(job: Job) {
  if (job.salary_min == null && job.salary_max == null)
    return "Salario por confirmar";
  const formatter = new Intl.NumberFormat("es-CO", {
    maximumFractionDigits: 0,
  });
  const amounts = [job.salary_min, job.salary_max]
    .filter((amount): amount is number => amount != null)
    .map((amount) => formatter.format(amount));
  const period =
    job.salary_period === "month" || job.salary_period === "monthly"
      ? "/ mes"
      : job.salary_period === "year" ||
          job.salary_period === "yearly" ||
          job.salary_period === "annual"
        ? "/ año"
        : job.salary_period === "hour" || job.salary_period === "hourly"
          ? "/ hora"
          : "";
  return `${job.currency || ""} ${amounts.join(" – ")} ${period}`.trim();
}

export function useAction(notify: Notify) {
  const client = useQueryClient();
  const [pending, setPending] = useState(false);
  const run = async (action: () => Promise<unknown>, success?: string) => {
    if (pending) return;
    setPending(true);
    try {
      await action();
      await client.invalidateQueries();
      if (success) notify({ kind: "success", message: success });
    } catch (error) {
      notify({
        kind: "error",
        message:
          error instanceof Error
            ? error.message
            : "No se pudo completar la operación.",
      });
    } finally {
      setPending(false);
    }
  };
  return { pending, run };
}

export function Spinner() {
  return <Loader2 size={17} className="spin" aria-label="Procesando" />;
}

export function Badge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: string;
}) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}

export function Empty({
  icon: Icon = Search,
  title,
  children,
  action,
}: {
  icon?: typeof Search;
  title: string;
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="empty-state">
      <div className="empty-icon">
        <Icon size={25} />
      </div>
      <h3>{title}</h3>
      <p>{children}</p>
      {action}
    </div>
  );
}

export function ErrorPanel({
  error,
  retry,
}: {
  error: unknown;
  retry: () => void;
}) {
  return (
    <div className="inline-error" role="alert">
      <CircleAlert size={19} />
      <span>
        {error instanceof Error
          ? error.message
          : "No pudimos cargar estos datos."}
      </span>
      <button className="text-button" onClick={retry}>
        Reintentar
      </button>
    </div>
  );
}

export function PageHeader({
  eyebrow,
  title,
  children,
  actions,
}: {
  eyebrow: string;
  title: string;
  children: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="page-heading">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <h1 className="text-balance">{title}</h1>
        <p>{children}</p>
      </div>
      <div className="heading-actions">{actions}</div>
    </div>
  );
}

export function CompanyMark({ company }: { company: string }) {
  const colors = [
    "company-teal",
    "company-blue",
    "company-orange",
    "company-purple",
  ];
  const index =
    [...company].reduce((total, char) => total + char.charCodeAt(0), 0) %
    colors.length;
  return (
    <span className={`company-mark ${colors[index]}`}>
      {company.slice(0, 1).toUpperCase()}
    </span>
  );
}

export function Modal({
  title,
  subtitle,
  children,
  onClose,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
  onClose: () => void;
}) {
  const closeRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    closeRef.current?.focus();
    const handler = (event: KeyboardEvent) => {
      if (event.key === "Escape") onCloseRef.current();
      if (event.key === "Tab" && panelRef.current) {
        const focusables = panelRef.current.querySelectorAll<HTMLElement>(
          'button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex="0"]',
        );
        const first = focusables[0];
        const last = focusables[focusables.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last?.focus();
        }
        if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first?.focus();
        }
      }
    };
    document.addEventListener("keydown", handler);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", handler);
      document.body.style.overflow = "";
      previous?.focus();
    };
  }, []);
  return (
    <div
      className="modal-backdrop"
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        ref={panelRef}
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
      >
        <div className="modal-heading">
          <div>
            {subtitle && <div className="eyebrow">{subtitle}</div>}
            <h2 id="modal-title">{title}</h2>
          </div>
          <button
            ref={closeRef}
            className="icon-button"
            aria-label="Cerrar diálogo"
            onClick={onClose}
          >
            <X size={22} />
          </button>
        </div>
        <div className="modal-body">{children}</div>
      </div>
    </div>
  );
}

export function StateBadge({ state }: { state: string }) {
  const tone = ["CONFIRMED", "ELIGIBLE"].includes(state)
    ? "teal"
    : ["PENDING_APPROVAL", "NEEDS_INFORMATION", "RETRY_PENDING"].includes(state)
      ? "orange"
      : ["FAILED", "REJECTED_BY_RULES"].includes(state)
        ? "red"
        : state === "SUBMITTED"
          ? "blue"
          : "neutral";
  return <Badge tone={tone}>{stateLabels[state] || state}</Badge>;
}

export function Toggle({
  title,
  description,
  checked,
  onChange,
}: {
  title: string;
  description: string;
  checked: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <label className="toggle-row">
      <span>
        <strong>{title}</strong>
        <small>{description}</small>
      </span>
      <input
        type="checkbox"
        className="switch-input"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
      />
      <span className="switch-track" aria-hidden="true">
        <span />
      </span>
    </label>
  );
}
