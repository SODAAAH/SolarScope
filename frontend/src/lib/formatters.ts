export function format12HourTime(ts: string | null | undefined, includeSeconds: boolean = false): string {
  if (!ts) return "";
  const trimmed = ts.trim();
  const timePart = trimmed.includes(" ") ? trimmed.split(" ")[1] : (trimmed.includes("T") ? trimmed.split("T")[1] : trimmed);
  if (!timePart) return trimmed;

  const parts = timePart.split(":");
  if (parts.length < 2) return trimmed;

  const hours = parseInt(parts[0], 10);
  const minutes = parts[1];
  const seconds = parts.length > 2 ? parts[2].split(".")[0] : null;

  if (isNaN(hours)) return trimmed;

  const period = hours >= 12 ? "PM" : "AM";
  const displayHours = hours % 12 === 0 ? 12 : hours % 12;

  if (includeSeconds && seconds !== null) {
    return `${displayHours}:${minutes}:${seconds} ${period}`;
  }
  return `${displayHours}:${minutes} ${period}`;
}

export function format12HourDateTime(ts: string | null | undefined, includeSeconds: boolean = false): string {
  if (!ts) return "";
  const trimmed = ts.trim();
  let datePart = "";
  if (trimmed.includes(" ")) {
    datePart = trimmed.split(" ")[0];
  } else if (trimmed.includes("T")) {
    datePart = trimmed.split("T")[0];
  }

  const timeStr = format12HourTime(trimmed, includeSeconds);
  if (datePart) {
    return `${datePart} ${timeStr}`;
  }
  return timeStr;
}

export function formatHourLabel12(hour: number): string {
  const h = Math.abs(Math.floor(hour)) % 24;
  if (h === 0) return "12 AM";
  if (h < 12) return `${h} AM`;
  if (h === 12) return "12 PM";
  return `${h - 12} PM`;
}

export function formatTimeRange12(start: string | null | undefined, end: string | null | undefined): string {
  if (!start && !end) return "";
  if (!start) return format12HourTime(end);
  if (!end) return format12HourTime(start);
  return `${format12HourTime(start)} - ${format12HourTime(end)}`;
}

