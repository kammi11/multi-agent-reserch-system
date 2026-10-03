import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "ResearchPilot AI",
  description: "An Agentic AI Research System for Evidence-Based Answers",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="shell">
          <header className="topbar">
            <Link href="/" className="brand">
              <span className="brand-mark">◆</span> ResearchPilot AI
            </Link>
            <nav>
              <Link href="/">New Research</Link>
              <Link href="/history">History</Link>
            </nav>
          </header>
          <main>{children}</main>
        </div>
      </body>
    </html>
  );
}
