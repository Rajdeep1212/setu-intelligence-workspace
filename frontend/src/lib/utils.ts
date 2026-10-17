import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// Language of a text by its script, for `lang` attributes and Bengali typography rules.
export function scriptLanguage(text: string): "bn" | "hi" | "en" {
  return /[\u0980-\u09ff]/.test(text) ? "bn" : /[\u0900-\u097f]/.test(text) ? "hi" : "en";
}
