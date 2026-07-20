import React, { ReactNode } from "react";

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
  testId?: string;
}

export default function PageHeader({ title, subtitle, actions, testId }: PageHeaderProps) {
  return (
    <div className="flex items-start justify-between gap-4 mb-6" data-testid={testId}>
      <div>
        <h1 className="font-display text-3xl font-bold tracking-tight text-zinc-950">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-zinc-500">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}
