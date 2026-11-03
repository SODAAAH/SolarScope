export function formatDateMMDDYYYY(d: string | Date | null | undefined): string {
  if (!d) return "";
  if (d instanceof Date) {
    if (isNaN(d.getTime())) return "";
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const dd = String(d.getDate()).padStart(2, "0");
    const yyyy = d.getFullYear();
    return `${mm}/${dd}/${yyyy}`;
  }
  const str = String(d).trim();
  const dateOnly = str.includes(" ") ? str.split(" ")[0] : (str.includes("T") ? str.split("T")[0] : str);
  const parts = dateOnly.split(/[-/]/);
  if (parts.length === 3) {
    if (parts[0].length === 4) {
      const [yyyy, mm, dd] = parts;
      return `${mm.padStart(2, "0")}/${dd.padStart(2, "0")}/${yyyy}`;
    } else if (parts[2].length === 4) {
      const [mm, dd, yyyy] = parts;
      return `${mm.padStart(2, "0")}/${dd.padStart(2, "0")}/${yyyy}`;
    }
  }
  const parsed = new Date(str);
  if (!isNaN(parsed.getTime())) {
    const mm = String(parsed.getMonth() + 1).padStart(2, "0");
    const dd = String(parsed.getDate()).padStart(2, "0");
    const yyyy = parsed.getFullYear();
    return `${mm}/${dd}/${yyyy}`;
  }
  return dateOnly;
}

export function formatDateText(text: string | null | undefined): string {
  if (!text) return "";
  return text.replace(/\b(\d{4})-(\d{2})-(\d{2})\b/g, "$2/$3/$1");
}

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

  const formattedDate = datePart ? formatDateMMDDYYYY(datePart) : "";
  const timeStr = format12HourTime(trimmed, includeSeconds);
  if (formattedDate) {
    return `${formattedDate} ${timeStr}`;
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
