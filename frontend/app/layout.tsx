import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Latch — Prospective memory for agents",
  description:
    "A Qwen-powered runtime that remembers what must happen, recognizes the right future cue, and acts exactly once under user control.",
  applicationName: "Latch / MementoVM",
  openGraph: {
    title: "Latch — Remember what must happen",
    description: "Typed, versioned, observable prospective memory for long-running agents.",
    type: "website",
  },
  twitter: { card: "summary_large_image" },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

