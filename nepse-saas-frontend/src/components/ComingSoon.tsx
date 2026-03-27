'use client';

import { Lock, Terminal, ArrowLeft } from 'lucide-react';
import Link from 'next/link';

interface Props {
  title: string;
  description: string;
}

export default function ComingSoon({ title, description }: Props) {
  return (
    <div className="flex min-h-[70vh] flex-col items-center justify-center gap-8 text-center">
      <div className="relative">
        <div className="absolute -inset-4 rounded-full bg-primary/5 blur-xl" />
        <div className="relative flex h-20 w-20 items-center justify-center rounded-2xl border border-primary/20 bg-surface-2/50 backdrop-blur">
          <Lock className="h-9 w-9 text-primary/60" />
        </div>
      </div>

      <div className="space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">{title}</h1>
        <p className="max-w-sm text-muted-foreground">{description}</p>
      </div>

      <div className="flex items-center gap-2 rounded-lg border border-border/50 bg-surface-2/40 px-4 py-3 text-sm font-mono text-muted-foreground">
        <Terminal className="h-4 w-4 text-primary/60 shrink-0" />
        <span>Available locally via CLI &nbsp;·&nbsp; <span className="text-foreground">nepse --help</span></span>
      </div>

      <Link
        href="/"
        className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Dashboard
      </Link>
    </div>
  );
}
