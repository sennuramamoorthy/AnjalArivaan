import clsx, { type ClassValue } from "clsx";

/** Tiny className joiner (we don't need tailwind-merge for this project). */
export function cn(...inputs: ClassValue[]): string {
  return clsx(inputs);
}
