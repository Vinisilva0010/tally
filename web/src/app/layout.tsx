import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Tally — carbon credit double counting",
  description:
    "Cross-registry audit of public carbon credit data, attested on Solana.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <header className="border-b-2 border-foreground">
          <div className="mx-auto flex max-w-5xl flex-wrap items-baseline gap-x-6 gap-y-2 px-6 py-5">
            <Link href="/" className="text-2xl font-extrabold no-underline text-foreground">
              Tally
            </Link>
            <span className="text-muted">
              Carbon credit double counting, checked against the public record
            </span>
            <nav className="ml-auto flex gap-5">
              <Link href="/">Findings</Link>
              <Link href="/queue">Review queue</Link>
            </nav>
          </div>
        </header>
        <main className="mx-auto max-w-5xl px-6 py-10">{children}</main>
        <footer className="mt-16 border-t border-border">
          <div className="mx-auto max-w-5xl px-6 py-8 text-muted">
            Data: Voluntary Registry Offsets Database v2026-08, Berkeley Carbon
            Trading Project, CC BY 4.0. Tally reports what the public data
            contains; a flagged pair is a case requiring explanation, not a
            finding of wrongdoing.
          </div>
        </footer>
      </body>
    </html>
  );
}
