import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AnjalArivaan — Takshashila University",
  description:
    "Personal assistant for Takshashila University — mail triage, meetings, travel, tasks, and AI-assisted briefings.",
  robots: { index: false, follow: false }, // internal-only app
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
