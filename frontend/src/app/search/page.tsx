"use client";

import { useState, useTransition } from "react";
import { PageHeader } from "@/components/layout/page-header";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useAccount } from "@/hooks/use-account";
import { searchApi } from "@/lib/endpoints";
import type { SearchHit } from "@/types/api";

const SOURCES = ["MAIL", "CALENDAR", "CONTACT", "TASK", "TRAVEL", "DOCUMENT"] as const;

export default function SearchPage() {
  const { accountId } = useAccount();
  const [q, setQ] = useState("");
  const [selected, setSelected] = useState<string[]>([...SOURCES]);
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [pending, startTransition] = useTransition();

  async function go(e: React.FormEvent) {
    e.preventDefault();
    if (!accountId || !q) return;
    startTransition(async () => {
      const res = await searchApi.query({
        q,
        account_id: accountId,
        sources: selected.join(","),
        size: 30,
      });
      setHits(res);
    });
  }

  return (
    <>
      <PageHeader
        title="Federated search"
        subtitle="Search across mail, calendar, tasks, travel, contacts and documents."
      />

      <form onSubmit={go} className="flex gap-2 mb-3">
        <Input
          placeholder="What are you looking for?"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          className="flex-1"
        />
        <Button type="submit" loading={pending}>
          Search
        </Button>
      </form>

      <div className="flex flex-wrap gap-2 mb-5">
        {SOURCES.map((s) => {
          const on = selected.includes(s);
          return (
            <button
              key={s}
              type="button"
              onClick={() =>
                setSelected(on ? selected.filter((x) => x !== s) : [...selected, s])
              }
              className={
                on
                  ? "px-3 py-1 rounded-full text-xs bg-brand-500 text-white"
                  : "px-3 py-1 rounded-full text-xs bg-ink-100 text-ink-700 hover:bg-ink-200"
              }
            >
              {s}
            </button>
          );
        })}
      </div>

      <div className="space-y-3">
        {hits.map((h) => (
          <Card key={`${h.source_type}:${h.id}`}>
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0 flex-1">
                <p className="font-medium text-ink-900">{h.title}</p>
                <p className="text-sm text-ink-600 mt-1 line-clamp-2">{h.preview}</p>
                {h.link && (
                  <a
                    href={h.link}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-brand-600 hover:underline mt-1 inline-block"
                  >
                    Open →
                  </a>
                )}
              </div>
              <div className="text-right">
                <Badge>{h.source_type}</Badge>
                <p className="text-xs text-ink-500 mt-1">
                  {(h.score * 100).toFixed(0)}%
                </p>
              </div>
            </div>
          </Card>
        ))}
      </div>

      {!pending && hits.length === 0 && q && (
        <Card>
          <p className="text-sm text-ink-500">No results.</p>
        </Card>
      )}
    </>
  );
}
