import { useEffect, useState } from "react";
import { Check, ExternalLink } from "lucide-react";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Breadcrumb, BreadcrumbItem, BreadcrumbLink, BreadcrumbList, BreadcrumbPage, BreadcrumbSeparator } from "@/components/ui/breadcrumb";
import { Button } from "@/components/ui/button";
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
  created: number;
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
  // one row per app: its latest version; replaced versions are under History on its details page (po, hq#781)
  const latest = new Map<string, App>();
  for (const a of (data?.people ?? []).flatMap((p) => p.apps)) {
    if (a.status === "refused") continue;
    const k = `${a.who.trim().toLowerCase()}\u0000${a.app}`;
    const cur = latest.get(k);
    // the live version wins (its link keeps working while a change builds); otherwise the newest
    const better = !cur || (a.status === "live") !== (cur.status === "live") ? !cur || a.status === "live" : a.created > cur.created;
    if (better) latest.set(k, a);
  }
  const apps = [...latest.values()].sort((x, y) => y.updated - x.updated);
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

const SPEC_LABELS: [string, string][] = [
  ["What it does and for whom", "What it does, for whom"],
  ["Screens / main actions", "Screens"],
  ["Data it reads and writes", "Data"],
  ["Done when", "Done when"],
  ["Out of scope", "Out of scope"],
  ["Asked for (their words)", "Asked for"],
];

function parseSpec(spec: string): { label: string; body: string }[] {
  // a changed app carries its earlier spec plus "## Change requested" sections: show the latest one
  const parts = spec.split(/\n## Change requested\n/);
  const latest = parts[parts.length - 1];
  const out: { label: string; body: string }[] = [];
  for (const [key, label] of SPEC_LABELS) {
    const esc = key.replace(/[.*+?^${}()|[\]\\/]/g, "\\$&");
    const m = latest.match(new RegExp(`\\*\\*${esc}:\\*\\*\\s*([\\s\\S]*?)(?=\\n\\*\\*[^*\\n]+:\\*\\*|$)`));
    if (m && m[1].trim()) out.push({ label, body: m[1].trim() });
  }
  return out.length ? out : [{ label: "Spec", body: latest.trim() }];
}

function when(ts: number) {
  return new Date(ts * 1000).toLocaleString("en-US", { timeZone: "America/Los_Angeles", hour: "numeric", minute: "2-digit", month: "short", day: "numeric" });
}

function Outcome({ v }: { v: App }) {
  if (v.status === "failed") return <span className="text-[#B42318] [overflow-wrap:anywhere]">Failed · {v.reason}</span>;
  if (v.status === "refused") return <span className="text-[#B42318] [overflow-wrap:anywhere]">Refused · {v.rule}</span>;
  if (["queued", "building", "deploying"].includes(v.status)) return <span className="text-[#4B5057]">{LABEL[v.status]}…</span>;
  return <span className="text-[#007A33]">Built{v.status === "stopped" ? " · since replaced or stopped" : ""}</span>;
}

function DetailView({ adminKey, id }: { adminKey: string; id: string }) {
  const [a, err] = usePoll<Full>(`/api/admin/${adminKey}/app/${id}`);
  const [stopErr, setStopErr] = useState("");
  const stop = async () => {
    setStopErr("");
    const r = await fetch(`/api/admin/${adminKey}/app/${id}/stop`, { method: "POST" });
    if (!r.ok) setStopErr(((await r.json().catch(() => ({}))) as { error?: string }).error || `The server answered ${r.status}.`);
  };
  const history = [...(a?.versions ?? [])].sort((x, y) => y.created - x.created);
  return (
    <div className="min-h-screen bg-white text-[#15171A] text-base">
      <div className="mx-auto max-w-7xl px-10 py-10">
        <Breadcrumb>
          <BreadcrumbList className="text-base">
            <BreadcrumbItem>
              <BreadcrumbLink href={`/admin/${adminKey}`}>← All apps</BreadcrumbLink>
            </BreadcrumbItem>
            <BreadcrumbSeparator />
            <BreadcrumbItem>
              <BreadcrumbPage>{a?.title ?? "…"}</BreadcrumbPage>
            </BreadcrumbItem>
          </BreadcrumbList>
        </Breadcrumb>
        {!a ? (
          <p className="mt-6 text-[#4B5057]">{err || "Loading…"}</p>
        ) : (
          <>
            <div className="mt-4 mb-8 flex flex-wrap items-center gap-4">
              <h1 className="text-3xl font-semibold [overflow-wrap:anywhere]">{a.title}</h1>
              <StatusBadge status={a.status} />
            </div>
            <div className="grid grid-cols-[1fr_340px] gap-10">
              <Card className="border-[#E3E5E8] shadow-none">
                <CardHeader>
                  <CardTitle className="text-lg">Spec</CardTitle>
                </CardHeader>
                <CardContent className="flex flex-col gap-6">
                  {parseSpec(a.spec).map((s) => (
                    <section key={s.label}>
                      <h3 className="mb-1 text-sm font-semibold uppercase tracking-wide text-[#4B5057]">{s.label}</h3>
                      {s.label === "Done when" ? (
                        <ul className="flex flex-col gap-1">
                          {s.body.split("\n").map((l) => l.replace(/^[-*]\s*/, "").trim()).filter(Boolean).map((l, i) => (
                            <li key={i} className="flex gap-2">
                              <Check className="mt-1 size-4 shrink-0 text-[#007A33]" />
                              <span className="[overflow-wrap:anywhere]">{l}</span>
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="whitespace-pre-wrap [overflow-wrap:anywhere]">{s.body}</p>
                      )}
                    </section>
                  ))}
                </CardContent>
              </Card>
              <aside className="flex flex-col gap-6">
                <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2">
                  <dt className="text-[#4B5057]">Owner</dt>
                  <dd>{a.who}</dd>
                  <dt className="text-[#4B5057]">Slot</dt>
                  <dd>{a.slot || "—"}</dd>
                  <dt className="text-[#4B5057]">Sandbox minutes</dt>
                  <dd>{a.minutes}</dd>
                  <dt className="text-[#4B5057]">Created</dt>
                  <dd>{when(a.created)}</dd>
                  <dt className="text-[#4B5057]">Updated</dt>
                  <dd>{ago(a.updated)}</dd>
                </dl>
                <div className="flex flex-col gap-2">
                  <Button variant="outline" className="w-full text-base" disabled={!(a.status === "live" && a.url)} asChild={a.status === "live" && !!a.url}>
                    {a.status === "live" && a.url ? (
                      <a href={a.url} target="_blank" rel="noreferrer">
                        Open <ExternalLink className="size-4" />
                      </a>
                    ) : (
                      <span>Open</span>
                    )}
                  </Button>
                  <AlertDialog>
                    <AlertDialogTrigger asChild>
                      <Button variant="outline" className="w-full border-[#B42318] text-base text-[#B42318] hover:text-[#B42318]" disabled={a.status !== "live"}>
                        Stop app
                      </Button>
                    </AlertDialogTrigger>
                    <AlertDialogContent>
                      <AlertDialogHeader>
                        <AlertDialogTitle>Stop {a.title}?</AlertDialogTitle>
                        <AlertDialogDescription>
                          Its link will show a "stopped" page. The code stays in {a.who}'s sandbox, so it can be built again.
                        </AlertDialogDescription>
                      </AlertDialogHeader>
                      <AlertDialogFooter>
                        <AlertDialogCancel>Cancel</AlertDialogCancel>
                        <AlertDialogAction onClick={stop} className="bg-[#B42318] text-white hover:bg-[#B42318]/90">
                          Stop app
                        </AlertDialogAction>
                      </AlertDialogFooter>
                    </AlertDialogContent>
                  </AlertDialog>
                  {stopErr && <p className="text-[#B42318] [overflow-wrap:anywhere]">{stopErr}</p>}
                </div>
                <div>
                  <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-[#4B5057]">History</h3>
                  <ol className="relative flex flex-col gap-5 border-l border-[#E3E5E8] pl-5">
                    {history.map((v) => (
                      <li key={v.id} className="relative">
                        <span
                          className={`absolute -left-[25px] top-1.5 size-2.5 rounded-full ${
                            v.status === "failed" || v.status === "refused" ? "bg-[#B42318]" : v.status === "live" ? "bg-[#007A33]" : "bg-[#4B5057]"
                          }`}
                        />
                        <div className="text-sm text-[#4B5057]">{when(v.created)}</div>
                        <div className="[overflow-wrap:anywhere]">“{v.ask}”</div>
                        <Outcome v={v} />
                      </li>
                    ))}
                  </ol>
                </div>
              </aside>
            </div>
          </>
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
