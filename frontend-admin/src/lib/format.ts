import { format } from "date-fns";

export function formatDuration(start: string | null, end: string | null): string {
  if (!start || !end) return "—";
  const ms = new Date(end).getTime() - new Date(start).getTime();
  const secs = Math.floor(ms / 1000);
  if (secs < 60) return `${secs}s`;
  const mins = Math.floor(secs / 60);
  const remainSecs = secs % 60;
  return `${mins}m ${remainSecs}s`;
}

export function formatDate(dateString: string | null, stringFormat: string = "MMM dd, HH:mm"): string {
  if (!dateString) return "—";
  return format(new Date(dateString), stringFormat);
}
