import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = {
  title: "MarketPulse | Market data, with context",
  description:
    "Historical market replay, Spark event-time analytics, and pipeline reliability. An independent engineering project.",
};
export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>{children}</body>
    </html>
  );
}
