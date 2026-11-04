"use client";

import { useQuery } from "@tanstack/react-query";
import {
  ArrowUpRight,
  CheckCircle2,
  ChevronRight,
  CircleAlert,
  Menu,
  ShieldCheck,
  Sparkles,
  Square,
  UserRound,
  X,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { type Dashboard } from "@/types";
import {
  useAction,
  type Section,
  type Notice,
  sections,
} from "@/components/shared";

import Overview from "@/features/dashboard/overview";
import JobsPanel from "@/features/jobs/jobs-panel";
import ApplicationsPanel from "@/features/applications/applications-panel";
import ProfilePanel from "@/features/cv/profile-panel";
import ContextPanel from "@/features/settings/context-panel";

export default function DashboardApp() {
  const [section, setSection] = useState<Section>("dashboard");
  const [mobileOpen, setMobileOpen] = useState(false);
  const [notice, setNotice] = useState<Notice | null>(null);
  const notify = useCallback((next: Notice) => setNotice(next), []);
  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(
      () => setNotice(null),
      notice.kind === "error" ? 12_000 : 5_000,
    );
    return () => clearTimeout(timer);
  }, [notice]);
  const me = useQuery({
    queryKey: ["me"],
    queryFn: () => api<{ full_name: string; email: string }>("/workspace"),
  });
  const dashboard = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => api<Dashboard>("/dashboard"),
    refetchInterval: 30_000,
  });
  const { run, pending } = useAction(notify);
  const go = (next: Section) => {
    setSection(next);
    setMobileOpen(false);
  };

  return (
    <div className="app-shell">
      {mobileOpen && (
        <button
          className="sidebar-backdrop"
          aria-label="Cerrar menú"
          onClick={() => setMobileOpen(false)}
        />
      )}
      <aside className={`sidebar ${mobileOpen ? "sidebar-open" : ""}`}>
        <a
          className="brand"
          href="#"
          onClick={(event) => {
            event.preventDefault();
            go("dashboard");
          }}
        >
          <span className="brand-symbol">
            <Sparkles size={23} />
          </span>
          <span>
            autojob<span className="brand-ai">AI</span>
            <small>EL SIGUIENTE PASO, CON CRITERIO.</small>
          </span>
        </a>
        <div className="workspace-label">MI ESPACIO DE TRABAJO</div>
        <nav aria-label="Navegación principal">
          {sections.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => go(id)}
              className={`nav-item ${section === id ? "active" : ""}`}
              aria-current={section === id ? "page" : undefined}
            >
              <Icon size={19} />
              <span>{label}</span>
              {id === "applications" &&
                (dashboard.data?.pending_approval ?? 0) > 0 && (
                  <span className="nav-count">
                    {dashboard.data?.pending_approval}
                  </span>
                )}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="control-card">
            <div className="control-heading">
              <ShieldCheck size={18} />
              <span>Tú tienes el control</span>
            </div>
            <p>Revisa tu perfil y las reglas antes de compartir información.</p>
            <button onClick={() => go("context")}>
              Ver mis reglas <ArrowUpRight size={14} />
            </button>
          </div>
          <div className="sidebar-status">
            <span
              className={`status-dot ${dashboard.data?.automation_enabled ? "on" : ""}`}
            />
            {dashboard.data?.automation_enabled
              ? "Automatización activa"
              : "Automatización en pausa"}
          </div>
          <button
            className="user-card"
            onClick={() => go("profile")}
            title="Editar mis datos"
          >
            <span className="avatar">
              {(me.data?.full_name || "P").slice(0, 1).toUpperCase()}
            </span>
            <span>
              <strong>{me.data?.full_name || "Mi perfil"}</strong>
              <small>{me.data?.email || "Espacio personal local"}</small>
            </span>
            <UserRound size={16} />
          </button>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div className="breadcrumb">
            <button
              className="icon-button mobile-menu"
              onClick={() => setMobileOpen(true)}
              aria-label="Abrir menú"
            >
              <Menu size={21} />
            </button>
            <span>Mi espacio</span>
            <ChevronRight size={14} />
            <strong>
              {sections.find((item) => item.id === section)?.label}
            </strong>
          </div>
          <div className="topbar-actions">
            <span className="private-label">
              <ShieldCheck size={15} />
              Espacio privado
            </span>
            <button
              className="stop-button"
              disabled={pending}
              onClick={() =>
                run(
                  () => api("/automation/stop", { method: "POST" }),
                  "Se detuvieron las nuevas automatizaciones.",
                )
              }
            >
              <Square size={12} fill="currentColor" />
              Parar
            </button>
          </div>
        </header>
        <main className="main-content" id="main-content">
          {section === "dashboard" && (
            <Overview
              data={dashboard.data}
              error={dashboard.error}
              loading={dashboard.isPending}
              retry={() => void dashboard.refetch()}
              go={go}
              notify={notify}
              name={me.data?.full_name}
            />
          )}
          {section === "jobs" && <JobsPanel notify={notify} go={go} />}
          {section === "applications" && <ApplicationsPanel notify={notify} />}
          {section === "profile" && <ProfilePanel notify={notify} />}
          {section === "context" && <ContextPanel notify={notify} />}
          <footer className="workspace-footer">
            <span>
              <Sparkles size={13} />
              Hechos reales. Decisiones informadas.
            </span>
            <span>AutoJob AI · Espacio personal</span>
          </footer>
        </main>
      </div>
      {notice && (
        <div
          className={`toast toast-${notice.kind}`}
          role={notice.kind === "error" ? "alert" : "status"}
        >
          {notice.kind === "error" ? (
            <CircleAlert size={21} />
          ) : (
            <CheckCircle2 size={21} />
          )}
          <span>{notice.message}</span>
          <button
            aria-label="Cerrar notificación"
            onClick={() => setNotice(null)}
          >
            <X size={17} />
          </button>
        </div>
      )}
    </div>
  );
}
