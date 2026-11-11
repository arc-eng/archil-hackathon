import { useEffect, useState } from "react";
import { ExternalLink } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";

type App = {
  id: string;
  app: string;
  title: string;
  who: string;
  ask: string;
  rule: string;
  status: string;
  reason: string;
  slot: string;
  url: string;
  updated: number;
  minutes: number;
  steps: string[];
  changes: number;
  current_url?: string;
};
type Person = { who: string; apps: App[]; minutes: number };
type Admin = { people: Person[]; refused: App[] };

const POLL_MS = 5000;

function usePoll<T>(url: string | null): [T | null, string] {
  const [data, setData] = useState<T | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    if (!url) return;
    let alive = true;
    const load = async () => {
      try {
        const r = await fetch(url, { cache: "no-store" });
        if (!r.ok) throw new Error(r.status === 404 ? "Not found." : `The server answered ${r.status}.`);
        const d = (await r.json()) as T;
        if (alive) {
          setData(d);
          setErr("");
        }
      } catch (e) {
        if (alive) setErr(e instanceof Error ? e.message : String(e));
      }
    };
    load();
    const t = setInterval(load, POLL_MS);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, [url]);
  return [data, err];
}

const LABEL: Record<string, string> = {
  queued: "Queued",
  building: "Building",
  deploying: "Deploying",
  live: "Live",
  stopping: "Stopping",
  stopped: "Stopped",
  failed: "Failed",
  refused: "Refused",
};

function StatusBadge({ status }: { status: string }) {
  const label = LABEL[status] ?? status;
  if (status === "live") return <Badge className="h-6 px-2.5 text-sm bg-[#007A33] text-white">{label}</Badge>;
  if (status === "failed" || status === "refused")
    return <Badge className="h-6 px-2.5 text-sm bg-[#B42318] text-white">{label}</Badge>;
  return (
    <Badge variant="secondary" className="h-6 px-2.5 text-sm">
      {label}
    </Badge>
  );
}

function ago(ts: number) {
  const s = Math.max(0, Math.round(Date.now() / 1000 - ts));
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  return `${Math.round(s / 3600)} h ago`;
}

function OpenLink({ url }: { url: string }) {
  return (
    <a href={url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 font-medium text-[#15171A] underline underline-offset-4">
      open <ExternalLink className="size-4" />
    </a>
  );
}

function AppRow({ a }: { a: App }) {
  return (
    <div className="flex items-start justify-between gap-6 py-3">
      <div className="min-w-0">
        <div className="font-medium text-[#15171A]">{a.title}</div>
        <div className="text-[#4B5057] break-words">
          {a.status === "failed" || a.status === "refused" ? a.reason : `“${a.ask}”`}
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-4 whitespace-nowrap">
        <span className="text-[#4B5057]">
          {a.minutes} min · {ago(a.updated)}
        </span>
        <StatusBadge status={a.status} />
        <span className="w-16 text-right">{a.status === "live" && a.url ? <OpenLink url={a.url} /> : null}</span>
      </div>
    </div>
  );
}

function AdminView({ adminKey }: { adminKey: string }) {
  const [data, err] = usePoll<Admin>(`/api/admin/${adminKey}`);
  return (
    <div className="min-h-screen bg-white text-[#15171A] text-base">
      <div className="mx-auto max-w-7xl px-10 py-10">
        <div className="mb-8 flex items-baseline justify-between">
          <h1 className="text-3xl font-semibold">Who is building what</h1>
          <span className="text-[#4B5057]">{err ? `⚠ ${err}` : "Updates every 5 s"}</span>
        </div>
        {!data ? (
          <p className="text-[#4B5057]">{err || "Loading…"}</p>
        ) : (
          <div className="grid grid-cols-[1fr_320px] gap-10">
            <section>
              {data.people.length === 0 && <p className="text-[#4B5057]">No one has asked for an app yet.</p>}
              {data.people.map((p, i) => {
                const apps = p.apps.filter((a) => a.status !== "refused");
                return (
                  <div key={p.who}>
                    {i > 0 && <Separator className="my-6 bg-[#E3E5E8]" />}
                    <div className="mb-1 flex items-baseline gap-3">
                      <h2 className="text-xl font-semibold">{p.who}</h2>
                      <span className="text-[#4B5057]">
                        own sandbox · {p.minutes} min · {apps.length} {apps.length === 1 ? "app" : "apps"}
                      </span>
                    </div>
                    {apps.length === 0 ? (
                      <p className="py-3 text-[#4B5057]">No apps built yet.</p>
                    ) : (
                      apps.map((a) => <AppRow key={a.id} a={a} />)
                    )}
                  </div>
                );
              })}
            </section>
            <aside>
              <Card className="border-[#E3E5E8] shadow-none">
                <CardHeader>
                  <CardTitle className="text-lg">Refused requests</CardTitle>
                </CardHeader>
                <CardContent className="flex flex-col gap-5">
                  {data.refused.length === 0 && <p className="text-[#4B5057]">None so far.</p>}
                  {data.refused.map((a) => (
                    <div key={a.id} className="flex flex-col gap-1">
                      <div>
                        <StatusBadge status="refused" />
                      </div>
                      <div className="break-words">“{a.ask}”</div>
                      <div className="text-[#4B5057]">by {a.who} · {ago(a.updated)}</div>
                      <div className="text-[#4B5057] break-words">{a.rule}</div>
                    </div>
                  ))}
                </CardContent>
              </Card>
            </aside>
          </div>
        )}
      </div>
    </div>
  );
}

function StatusView({ id }: { id: string }) {
  const [a, err] = usePoll<App>(`/api/status/${id}`);
  return (
    <div className="min-h-screen bg-white text-[#15171A] text-base">
      <div className="mx-auto w-full max-w-2xl px-4 py-8 sm:px-6 sm:py-10">
        {!a ? (
          <p className="text-[#4B5057]">{err || "Loading…"}</p>
        ) : (
          <Card className="min-w-0 border-[#E3E5E8] shadow-none">
            <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-3">
              <CardTitle className="min-w-0 text-2xl [overflow-wrap:anywhere]">{a.title}</CardTitle>
              <StatusBadge status={a.status} />
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <p className="text-[#4B5057] [overflow-wrap:anywhere]">
                For {a.who} · “{a.ask}”
              </p>
              {a.status === "live" && a.url && (
                <a href={a.url} target="_blank" rel="noreferrer" className="inline-flex w-fit items-center gap-2 rounded-md bg-[#007A33] px-4 py-2 font-medium text-white">
                  Open the app <ExternalLink className="size-4" />
                </a>
              )}
              {(a.status === "failed" || a.status === "refused") && <p className="text-[#B42318] [overflow-wrap:anywhere]">{a.reason}</p>}
              {a.status === "stopped" && (
                <p className="text-[#4B5057] [overflow-wrap:anywhere]">
                  {a.reason}
                  {a.current_url && (
                    <>
                      {" · "}
                      <a href={a.current_url} target="_blank" rel="noreferrer" className="font-medium text-[#15171A] underline underline-offset-4">
                        open the current version
                      </a>
                    </>
                  )}
                </p>
              )}
              <Separator className="bg-[#E3E5E8]" />
              <ol className="flex flex-col gap-1 text-[#4B5057]">
                {a.steps.map((s, i) => (
                  <li key={i} className="[overflow-wrap:anywhere]">
                    {s}
                  </li>
                ))}
              </ol>
              <p className="text-sm text-[#4B5057]">{err ? `⚠ ${err}` : "This page updates every 5 s."}</p>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}

export default function App() {
  const [, kind, arg] = window.location.pathname.split("/");
  if (kind === "admin" && arg) return <AdminView adminKey={arg} />;
  if (kind === "status" && arg) return <StatusView id={arg} />;
  return <p className="p-10">Not found.</p>;
}
