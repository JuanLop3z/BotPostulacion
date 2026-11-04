import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AutoJob AI · Tu próximo paso",
  description:
    "Tu espacio para encontrar oportunidades, revisar tu perfil y gestionar candidaturas con criterio.",
  robots: { index: false, follow: false },
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="es">
      <body>{children}</body>
    </html>
  );
}
