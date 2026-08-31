import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = { title: { default: "SETU Intelligence Workspace", template: "%s · SETU" }, description: "Evidence-backed intelligence for India’s digital public infrastructure." };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) { return <html lang="en" suppressHydrationWarning><body>{children}</body></html>; }
