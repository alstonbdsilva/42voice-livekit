export const cn = (...classes: any[]) => classes.filter(Boolean).join(' ');

export const formatApiErrorDetail = (detail: any) => {
  if (!detail) return "An error occurred";
  if (typeof detail === "string") return detail;
  return JSON.stringify(detail);
};

export const fmtCurrency = (value: any) => {
  if (value === undefined || value === null) return ".00";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
};

export const fmtNumber = (value: any) => {
  if (value === undefined || value === null) return "0";
  return new Intl.NumberFormat("en-US").format(value);
};

export const fmtDate = (date: any) => {
  if (!date) return "";
  const d = typeof date === "string" ? new Date(date) : date;
  return d.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
};

export const fmtDateTime = (date: any) => {
  if (!date) return "";
  const d = typeof date === "string" ? new Date(date) : date;
  return d.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
};

export const daysFrom = (date: any) => {
  if (!date) return 0;
  const d = typeof date === "string" ? new Date(date) : date;
  const now = new Date();
  const diff = d.getTime() - now.getTime();
  return Math.ceil(diff / (1000 * 60 * 60 * 24));
};
