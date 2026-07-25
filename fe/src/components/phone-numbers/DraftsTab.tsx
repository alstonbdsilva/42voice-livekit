import React from "react";
import { Phone, Trash2, Edit2 } from "lucide-react";

interface DraftsTabProps {
  numbers: any[];
  onEdit: (item: any) => void;
  onDelete: (id: string, numStr: string) => void;
}

export function DraftsTab({ numbers, onEdit, onDelete }: DraftsTabProps) {
  if (numbers.length === 0) {
    return (
      <div className="border border-dashed border-zinc-200 bg-white p-12 text-center rounded-sm">
        <Phone className="w-10 h-10 text-zinc-300 mx-auto mb-3" />
        <h3 className="font-bold text-sm text-zinc-950">No draft DIDs</h3>
        <p className="text-xs text-zinc-500 mt-1 max-w-xs mx-auto">
          No offline or draft status phone numbers registered.
        </p>
      </div>
    );
  }

  return (
    <div className="bg-white border border-zinc-200 rounded-sm overflow-hidden shadow-xs">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-zinc-50 text-zinc-500 uppercase text-[10px] tracking-wider border-b border-zinc-200 font-bold">
            <th className="px-5 py-3 text-left">Phone Number</th>
            <th className="px-5 py-3 text-left">Friendly Label</th>
            <th className="px-5 py-3 text-left">Carrier</th>
            <th className="px-5 py-3 text-center">Status</th>
            <th className="px-5 py-3 text-right">Price</th>
            <th className="px-5 py-3 text-center">Actions</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-zinc-200">
          {numbers.map((num) => (
            <tr key={num.id} className="hover:bg-zinc-50/50 transition-colors">
              <td className="px-5 py-4 whitespace-nowrap">
                <div className="flex items-center gap-2">
                  <Phone className="w-4 h-4 text-zinc-400" />
                  <span className="font-mono font-medium text-zinc-900">{num.number}</span>
                </div>
              </td>
              <td className="px-5 py-4 whitespace-nowrap text-zinc-700 font-medium text-xs">{num.name}</td>
              <td className="px-5 py-4 whitespace-nowrap">
                <span className="inline-flex items-center px-1.5 py-0.5 text-[9px] font-bold rounded-sm uppercase tracking-wider bg-zinc-100 text-zinc-800 border border-zinc-200">
                  {num.provider}
                </span>
              </td>
              <td className="px-5 py-4 whitespace-nowrap text-center">
                <span className="inline-block px-2 py-0.5 rounded-sm text-[10px] font-bold uppercase tracking-wider border bg-amber-50 text-amber-700 border-amber-200">
                  Draft / Offline
                </span>
              </td>
              <td className="px-5 py-4 whitespace-nowrap text-right text-zinc-900 font-medium font-mono text-xs">
                {num.monthlyCost}/mo
              </td>
              <td className="px-5 py-4 whitespace-nowrap text-center">
                <div className="flex items-center justify-center gap-2">
                  <button
                    onClick={() => onEdit(num)}
                    className="text-zinc-400 hover:text-zinc-950 p-1 transition-colors"
                    title="Edit Line Details"
                  >
                    <Edit2 className="w-3.5 h-3.5" />
                  </button>
                  <button
                    onClick={() => onDelete(num.id, num.number)}
                    className="text-zinc-400 hover:text-red-600 p-1 transition-colors"
                    title="Delete Draft"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default DraftsTab;
