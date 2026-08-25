import { format, isValid } from "date-fns";

function parseDate(value: string): Date | null {
  const date = new Date(value);
  return isValid(date) ? date : null;
}

function utcCalendarDate(date: Date): Date {
  return new Date(
    date.getUTCFullYear(),
    date.getUTCMonth(),
    date.getUTCDate(),
    date.getUTCHours(),
    date.getUTCMinutes(),
  );
}

export function formatProbability(value: number | null): string {
  if (value === null) return "Withheld";
  return `${(value * 100).toFixed(1)}%`;
}

export function formatSignedProbability(value: number | null): string {
  if (value === null) return "—";
  const percentagePoints = value * 100;
  const sign = percentagePoints > 0 ? "+" : percentagePoints < 0 ? "−" : "";
  return `${sign}${Math.abs(percentagePoints).toFixed(1)} pp`;
}

export function formatCompactNumber(value: number): string {
  if (Math.abs(value) < 1_000) return new Intl.NumberFormat("en-US").format(value);
  return new Intl.NumberFormat("en-US", {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(value);
}

export function formatDate(value: string): string {
  const date = parseDate(value);
  if (!date) return "Unavailable";
  return format(utcCalendarDate(date), "dd MMM yyyy");
}

export function formatDateTime(value: string | null): string {
  if (value === null) return "Never";
  const date = parseDate(value);
  if (!date) return "Unavailable";
  return `${format(utcCalendarDate(date), "dd MMM yyyy, HH:mm")} UTC`;
}
