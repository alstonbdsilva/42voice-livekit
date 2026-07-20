import React, { useMemo, useState } from "react";
import { ChevronDown, Search } from "lucide-react";

export interface Column<T> {
  key: string;
  label: string;
  render?: (row: T) => React.ReactNode;
}

export interface FilterOption {
  value: string;
  label: string;
}

export interface Filter {
  key: string;
  label: string;
  options: FilterOption[];
}

interface DataTableProps<T> {
  columns: Column<T>[];
  rows: T[];
  searchKeys?: string[];
  filters?: Filter[];
  emptyText?: string;
  onRowClick?: (row: T) => void;
  testId?: string;
}

export default function DataTable<T extends Record<string, any>>({
  columns,
  rows,
  searchKeys = [],
  filters = [],
  emptyText = "No data",
  onRowClick,
  testId,
}: DataTableProps<T>) {
  const [q, setQ] = useState("");
  const [filterValues, setFilterValues] = useState<Record<string, string>>({});

  const filtered = useMemo(() => {
    let r = Array.isArray(rows) ? rows : [];
    if (q && searchKeys.length) {
      const lq = q.toLowerCase();
      r = r.filter((row) =>
        searchKeys.some((k) => String(row[k] ?? "").toLowerCase().includes(lq))
      );
    }
    Object.entries(filterValues).forEach(([k, v]) => {
      if (v && v !== "all") {
        r = r.filter((row) => row[k] === v);
      }
    });
    return r;
  }, [rows, q, filterValues, searchKeys]);

  return (
    <div className="bg-white border border-zinc-200" data-testid={testId}>
      <div className="px-4 py-3 border-b border-zinc-200 flex flex-wrap items-center gap-3">
        {searchKeys.length > 0 && (
          <div className="relative">
            <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-zinc-400" />
            <input
              data-testid={`${testId}-search`}
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search…"
              className="bg-zinc-50 border border-zinc-200 rounded-sm pl-8 pr-3 py-1.5 text-sm w-60 focus:outline-none focus:border-zinc-950 focus:bg-white"
            />
          </div>
        )}
        {filters.map((f) => (
          <div key={f.key} className="relative">
            <select
              data-testid={`${testId}-filter-${f.key}`}
              value={filterValues[f.key] || "all"}
              onChange={(e) => setFilterValues({ ...filterValues, [f.key]: e.target.value })}
              className="appearance-none bg-zinc-50 border border-zinc-200 rounded-sm pl-3 pr-8 py-1.5 text-sm focus:outline-none focus:border-zinc-950"
            >
              <option value="all">{`${f.label}: All`}</option>
              {f.options.map((o) => (
                <option key={o.value} value={o.value}>{`${f.label}: ${o.label}`}</option>
              ))}
            </select>
            <ChevronDown className="w-3.5 h-3.5 absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none text-zinc-500" />
          </div>
        ))}
        <div className="ml-auto label-tiny font-mono-stat">{filtered.length} {filtered.length === 1 ? "record" : "records"}</div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr>
              {columns.map((c) => (
                <th key={c.key} className="px-4 py-2.5 text-left label-tiny bg-zinc-50 border-b border-zinc-200 whitespace-nowrap">
                  {c.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="px-4 py-10 text-center text-zinc-400 text-sm" data-testid={`${testId}-empty`}>
                  {emptyText}
                </td>
              </tr>
            ) : (
              filtered && filtered?.map((row, idx) => (
                <tr
                  key={row.id || idx}
                  onClick={onRowClick ? () => onRowClick(row) : undefined}
                  className={`border-b border-zinc-100 hover:bg-zinc-50 transition-colors ${onRowClick ? "cursor-pointer" : ""}`}
                  data-testid={`${testId}-row-${idx}`}
                >
                  {columns.map((c) => (
                    <td key={c.key} className="px-4 py-3 text-zinc-900 align-top">
                      {c.render ? c.render(row) : (row[c.key] ?? "—")}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
