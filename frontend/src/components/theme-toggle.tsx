"use client";
import { Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";

export function ThemeToggle({ compact = false }: { compact?: boolean }) {
  const [theme, setTheme] = useState<"light" | "dark">("light");
  useEffect(() => { const saved = localStorage.getItem("setu-theme") === "dark" ? "dark" : "light"; document.documentElement.dataset.theme = saved; const frame = requestAnimationFrame(() => setTheme(saved)); return () => cancelAnimationFrame(frame); }, []);
  const toggle = () => { const next = theme === "light" ? "dark" : "light"; setTheme(next); document.documentElement.dataset.theme = next; localStorage.setItem("setu-theme", next); };
  return <button type="button" className="icon-action" onClick={toggle} aria-label={`Switch to ${theme === "light" ? "dark" : "light"} theme`}>{theme === "light" ? <Moon size={16} /> : <Sun size={16} />}{!compact && <span>{theme === "light" ? "Dark" : "Light"}</span>}</button>;
}
