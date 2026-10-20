import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "MatchLens AI · Football Intelligence You Can Challenge",
  description:
    "Inspect the events behind a football insight. A continuous synthetic match, deterministic statistics and independent Analyst / Verifier agents.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
