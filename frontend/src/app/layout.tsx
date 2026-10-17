import type { Metadata } from "next";
import { Inter, Noto_Sans_Bengali } from "next/font/google";
import "./globals.css";
const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });
// Not preloaded: the browser fetches it only when a page contains Bengali (unicode-range).
const notoBengali = Noto_Sans_Bengali({ subsets: ["bengali"], variable: "--font-bengali", preload: false });
export const metadata: Metadata = { title: { default: "SETU Intelligence Workspace", template: "%s · SETU" }, description: "Evidence-backed intelligence for India’s digital public infrastructure." };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) { return <html lang="en" className={`${inter.variable} ${notoBengali.variable}`} suppressHydrationWarning><body>{children}</body></html>; }
