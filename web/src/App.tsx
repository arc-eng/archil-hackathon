import { useEffect, useState } from "react";
import { ExternalLink } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

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

function Stat({ label, value, tone }: { label: string; value: string | number; tone?: "live" | "bad" }) {
  const color = tone === "live" ? "text-[#007A33]" : tone === "bad" ? "text-[#B42318]" : "text-[#15171A]";
  return (
    <Card className="border-[#E3E5E8] shadow-none">
      <CardContent className="flex flex-col gap-1">
        <span className="text-[#4B5057]">{label}</span>
        <span className={`text-3xl font-semibold ${color}`}>{value}</span>
      </CardContent>
    </Card>
  );
}

function AdminView({ adminKey }: { adminKey: string }) {
  const [data, err] = usePoll<Admin>(`/api/admin/${adminKey}`);
  const apps = (data?.people ?? []).flatMap((p) => p.apps).filter((a) => a.status !== "refused");
  apps.sort((x, y) => y.updated - x.updated);
  const refused = data?.refused ?? [];
  const minutes = Math.round((data?.people ?? []).reduce((s, p) => s + p.minutes, 0) * 10) / 10;
  const open = (a: App) => {
    window.location.href = `/admin/${adminKey}/app/${a.id}`;
  };
  return (
    <div className="min-h-screen bg-white text-[#15171A] text-base">
      <div className="mx-auto max-w-7xl px-10 py-10">
        <div className="mb-6 flex items-baseline justify-between">
          <h1 className="text-3xl font-semibold">Apps</h1>
          <span className="text-[#4B5057]">{err ? `⚠ ${err}` : "Updates every 5 s"}</span>
        </div>
        {!data ? (
          <p className="text-[#4B5057]">{err || "Loading…"}</p>
        ) : (
          <>
            <div className="mb-8 grid grid-cols-5 gap-4">
              <Stat label="People" value={data.people.length} />
              <Stat label="Live apps" value={apps.filter((a) => a.status === "live").length} tone="live" />
              <Stat label="Building now" value={apps.filter((a) => ["queued", "building", "deploying"].includes(a.status)).length} />
              <Stat label="Refused" value={refused.length} tone={refused.length ? "bad" : undefined} />
              <Stat label="Sandbox minutes" value={minutes} />
            </div>
            <Tabs defaultValue="apps">
              <TabsList>
                <TabsTrigger value="apps" className="text-base">Apps ({apps.length})</TabsTrigger>
                <TabsTrigger value="refused" className="text-base">Refused requests ({refused.length})</TabsTrigger>
              </TabsList>
              <TabsContent value="apps">
                <Table className="text-base">
                  <TableHeader>
                    <TableRow>
                      <TableHead>App</TableHead>
                      <TableHead>Owner</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead className="text-right">Minutes</TableHead>
                      <TableHead>Updated</TableHead>
                      <TableHead>Link</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {apps.length === 0 && (
                      <TableRow>
                        <TableCell colSpan={6} className="py-6 text-[#4B5057]">No apps yet.</TableCell>
                      </TableRow>
                    )}
                    {apps.map((a) => (
                      <TableRow key={a.id} onClick={() => open(a)} className="cursor-pointer">
                        <TableCell className="max-w-[420px] whitespace-normal">
                          <div className="font-medium">{a.title}</div>
                          {a.status === "failed" && a.reason && <div className="text-[#4B5057] [overflow-wrap:anywhere]">{a.reason}</div>}
                        </TableCell>
                        <TableCell>{a.who}</TableCell>
                        <TableCell><StatusBadge status={a.status} /></TableCell>
                        <TableCell className="text-right tabular-nums">{a.minutes}</TableCell>
                        <TableCell className="text-[#4B5057]">{ago(a.updated)}</TableCell>
                        <TableCell onClick={(e) => e.stopPropagation()}>
                          {a.status === "live" && a.url ? <OpenLink url={a.url} /> : null}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TabsContent>
              <TabsContent value="refused">
                <Table className="text-base">
                  <TableHeader>
                    <TableRow>
                      <TableHead>Asked for</TableHead>
                      <TableHead>By</TableHead>
                      <TableHead>Rule</TableHead>
                      <TableHead>When</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {refused.length === 0 && (
                      <TableRow>
                        <TableCell colSpan={4} className="py-6 text-[#4B5057]">None so far.</TableCell>
                      </TableRow>
                    )}
                    {refused.map((a) => (
                      <TableRow key={a.id} onClick={() => open(a)} className="cursor-pointer">
                        <TableCell className="max-w-[420px] whitespace-normal [overflow-wrap:anywhere]">“{a.ask}”</TableCell>
                        <TableCell>{a.who}</TableCell>
                        <TableCell className="max-w-[360px] whitespace-normal text-[#B42318]">{a.rule}</TableCell>
                        <TableCell className="text-[#4B5057]">{ago(a.updated)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TabsContent>
            </Tabs>
          </>
        )}
      </div>
    </div>
  );
}

type Full = App & { spec: string; versions: App[] };

function DetailView({ adminKey, id }: { adminKey: string; id: string }) {
  const [a, err] = usePoll<Full>(`/api/admin/${adminKey}/app/${id}`);
  return (
    <div className="min-h-screen bg-white text-[#15171A] text-base">
      <div className="mx-auto max-w-4xl px-10 py-10">
        <a href={`/admin/${adminKey}`} className="text-[#4B5057] underline underline-offset-4">← All apps</a>
        {!a ? (
          <p className="mt-6 text-[#4B5057]">{err || "Loading…"}</p>
        ) : (
          <div className="mt-6 flex flex-col gap-6">
            <div className="flex flex-wrap items-center gap-4">
              <h1 className="text-3xl font-semibold [overflow-wrap:anywhere]">{a.title}</h1>
              <StatusBadge status={a.status} />
              {a.status === "live" && a.url && <OpenLink url={a.url} />}
            </div>
            <p className="text-[#4B5057]">
              {a.who} · {a.minutes} sandbox min · {a.slot || "no slot"} · updated {ago(a.updated)}
            </p>
            {(a.status === "failed" || a.status === "refused") && <p className="text-[#B42318] [overflow-wrap:anywhere]">{a.rule || a.reason}</p>}
            <Card className="border-[#E3E5E8] shadow-none">
              <CardHeader><CardTitle className="text-lg">Spec</CardTitle></CardHeader>
              <CardContent>
                <pre className="whitespace-pre-wrap font-sans text-base [overflow-wrap:anywhere]">{a.spec}</pre>
              </CardContent>
            </Card>
            <Card className="border-[#E3E5E8] shadow-none">
              <CardHeader><CardTitle className="text-lg">Build steps</CardTitle></CardHeader>
              <CardContent>
                <ol className="flex flex-col gap-1 text-[#4B5057]">
                  {a.steps.map((s, i) => <li key={i} className="[overflow-wrap:anywhere]">{s}</li>)}
                </ol>
              </CardContent>
            </Card>
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
  const [, kind, arg, sub, id] = window.location.pathname.split("/");
  if (kind === "admin" && arg && sub === "app" && id) return <DetailView adminKey={arg} id={id} />;
  if (kind === "admin" && arg) return <AdminView adminKey={arg} />;
  if (kind === "status" && arg) return <StatusView id={arg} />;
  return <p className="p-10">Not found.</p>;
}
