import { useEffect, useState } from "react";
import { Activity, Check, ExternalLink, HeartPulse, Wallet } from "lucide-react";
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
import archilIcon from "@/assets/brand/archil.svg";
import cloudBuildIcon from "@/assets/brand/cloud-build.svg";
import cloudLoggingIcon from "@/assets/brand/cloud-logging.svg";
import cloudRunIcon from "@/assets/brand/cloud-run.svg";
import githubIcon from "@/assets/brand/github.svg";
import { Badge } from "@/components/ui/badge";
import { Breadcrumb, BreadcrumbItem, BreadcrumbLink, BreadcrumbList, BreadcrumbPage, BreadcrumbSeparator } from "@/components/ui/breadcrumb";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

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
  golden?: number;
  current_url?: string;
};
type Person = { who: string; apps: App[]; minutes: number };
type Link = { label: string; url: string };
type Admin = { people: Person[]; refused: App[]; golden?: number | null; golden_pending?: string[]; links?: Link[] };

// each console's own icon (Marco, hq#782, 8:18 pm): GitHub's mark, Google Cloud's official icons (Cloud Run has its own;
// Cloud Build and Logging use their DevOps / Observability category icons, as Google's icon guide says), Archil's logo
const JUMP_ICONS: Record<string, string> = {
  "Golden image": githubIcon,
  "App servers": cloudRunIcon,
  Deploys: cloudBuildIcon,
  Logs: cloudLoggingIcon,
  Sandboxes: archilIcon,
};

// quick-jump buttons into the consoles (Marco, hq#782): each opens in a new tab, in that console's own sign-in
function JumpButton({ link, full }: { link: Link; full?: boolean }) {
  return (
    <Button variant="outline" className={`text-base ${full ? "w-full justify-between" : ""}`} asChild>
      <a href={link.url} target="_blank" rel="noreferrer">
        {JUMP_ICONS[link.label] && <img src={JUMP_ICONS[link.label]} alt="" className="size-5 shrink-0" />}
        <span className="mr-auto truncate">{link.label}</span> <ExternalLink className="size-4 shrink-0" />
      </a>
    </Button>
  );
}

const JUMP_WORDS: Record<string, string> = {
  "Golden image": "The setup every sandbox starts from: tools, house rules, brand.",
  "App servers": "Each live app's own server on Google Cloud.",
  Deploys: "Every build and deploy by the company's builder.",
  Logs: "What the apps are doing, errors included.",
  Sandboxes: "Each person's own Archil sandbox, where their apps are built.",
};

// the personas' faces (Marco, hq#782): web/public/personas/personas.json, filled in by the designer; anyone not in
// it (Marco himself, a new name) gets an initials circle
type Persona = { name: string; role?: string; face?: string; admin?: boolean };
let personasLoad: Promise<Record<string, Persona>> | null = null;
function usePersonas() {
  const [map, setMap] = useState<Record<string, Persona>>({});
  useEffect(() => {
    personasLoad ??= fetch("/personas/personas.json")
      .then((r) => (r.ok ? r.json() : []))
      .then((list: Persona[]) => Object.fromEntries((Array.isArray(list) ? list : []).map((p) => [p.name.trim().toLowerCase(), p])))
      .catch(() => ({}));
    let alive = true;
    personasLoad.then((m) => alive && setMap(m));
    return () => {
      alive = false;
    };
  }, []);
  return map;
}

function Owner({ who, size = 28 }: { who: string; size?: number }) {
  const p = usePersonas()[who.trim().toLowerCase()];
  const [broken, setBroken] = useState(false);
  const initials = who.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]?.toUpperCase()).join("");
  return (
    <span className="inline-flex items-center gap-2">
      {p?.face && !broken ? (
        <img src={`/personas/${p.face}`} alt="" width={size} height={size} onError={() => setBroken(true)} className="shrink-0 rounded-full bg-[#E3E5E8] object-cover" style={{ width: size, height: size }} />
      ) : (
        <span className="inline-flex shrink-0 items-center justify-center rounded-full bg-[#E3E5E8] text-xs font-semibold text-[#4B5057]" style={{ width: size, height: size }}>
          {initials}
        </span>
      )}
      <span>{who}</span>
    </span>
  );
}

// "signed in as" the admin persona, top right (Marco, hq#782, 8:10 pm). Visual only: there is no sign-in behind it
function SignedIn() {
  const sam = Object.values(usePersonas()).find((p) => p.admin);
  if (!sam) return null;
  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-[#E3E5E8] py-1 pr-4 pl-1">
      <Owner who={sam.name} size={32} />
      {sam.role && <span className="text-sm text-[#4B5057]">{sam.role}</span>}
    </span>
  );
}

// Marco's classic SaaS frame (hq#782, 8:24 pm): navbar on top (name + Sam), sidebar with Quick access then Builders
function Shell({ adminKey, data, who, children }: { adminKey: string; data: Admin | null; who: string; children: React.ReactNode }) {
  const personas = usePersonas();
  const counts = new Map<string, { name: string; n: number }>();
  for (const p of Object.values(personas)) if (!p.admin) counts.set(p.name.trim().toLowerCase(), { name: p.name, n: 0 });
  for (const a of latestApps(data)) {
    const k = a.who.trim().toLowerCase();
    const c = counts.get(k) ?? { name: a.who, n: 0 };
    counts.set(k, { ...c, n: c.n + 1 });
  }
  const builders = [...counts.values()].sort((x, y) => y.n - x.n || x.name.localeCompare(y.name));
  const base = `/admin/${adminKey}`;
  return (
    <div className="flex min-h-screen flex-col bg-white text-base text-[#15171A]">
      <header className="flex h-16 shrink-0 items-center justify-between border-b border-[#E3E5E8] px-6">
        <a href={base} className="text-xl font-semibold">Golden Sandbox</a>
        <SignedIn />
      </header>
      <div className="flex flex-1">
        <aside className="flex w-72 shrink-0 flex-col gap-8 border-r border-[#E3E5E8] bg-[#F7F8F9] px-4 py-6">
          <nav>
            <h2 className="mb-2 px-2 text-xs font-semibold uppercase tracking-wide text-[#4B5057]">Quick access</h2>
            <ul className="flex flex-col gap-0.5">
              {(data?.links ?? []).map((l) => (
                <li key={l.label}>
                  <a href={l.url} target="_blank" rel="noreferrer" title={JUMP_WORDS[l.label]} className="group flex items-center gap-3 rounded-md px-2 py-2 hover:bg-[#ECEEF0]">
                    {JUMP_ICONS[l.label] && <img src={JUMP_ICONS[l.label]} alt="" className="size-5 shrink-0" />}
                    <span className="flex-1 truncate">{l.label}</span>
                    <ExternalLink className="size-4 shrink-0 text-[#9AA0A6] group-hover:text-[#4B5057]" />
                  </a>
                </li>
              ))}
            </ul>
          </nav>
          <nav>
            <h2 className="mb-2 px-2 text-xs font-semibold uppercase tracking-wide text-[#4B5057]">Monitoring</h2>
            <ul className="flex flex-col gap-0.5">
              {MONITOR_PAGES.map((m) => {
                const on = window.location.pathname === `${base}/monitoring/${m.page}`;
                return (
                  <li key={m.page}>
                    <a href={`${base}/monitoring/${m.page}`} className={`flex items-center gap-3 rounded-md px-2 py-2 ${on ? "bg-[#E3E5E8] font-medium" : "hover:bg-[#ECEEF0]"}`}>
                      <m.icon className="size-5 shrink-0 text-[#4B5057]" />
                      <span className="flex-1 truncate">{m.label}</span>
                    </a>
                  </li>
                );
              })}
            </ul>
          </nav>
          <nav>
            <h2 className="mb-2 px-2 text-xs font-semibold uppercase tracking-wide text-[#4B5057]">Builders</h2>
            <ul className="flex flex-col gap-0.5">
              {builders.map((b) => {
                const on = who.trim().toLowerCase() === b.name.trim().toLowerCase();
                return (
                  <li key={b.name}>
                    <a
                      href={on ? base : `${base}?who=${encodeURIComponent(b.name)}`}
                      className={`flex items-center justify-between gap-2 rounded-md px-2 py-1.5 ${on ? "bg-[#E3E5E8] font-medium" : "hover:bg-[#ECEEF0]"}`}
                    >
                      <Owner who={b.name} />
                      <span className="text-sm tabular-nums text-[#4B5057]">{b.n}</span>
                    </a>
                  </li>
                );
              })}
            </ul>
          </nav>
        </aside>
        <main className="min-w-0 flex-1 px-10 py-8">{children}</main>
      </div>
    </div>
  );
}

// one row per app: its latest version; replaced versions are under History on its details page (po, hq#781)
function latestApps(data: Admin | null): App[] {
  const latest = new Map<string, App>();
  for (const a of (data?.people ?? []).flatMap((p) => p.apps)) {
    if (a.status === "refused") continue;
    const k = `${a.who.trim().toLowerCase()}\u0000${a.app}`;
    const cur = latest.get(k);
    // the live version wins (its link keeps working while a change builds); otherwise the newest
    const better = !cur || (a.status === "live") !== (cur.status === "live") ? !cur || a.status === "live" : a.created > cur.created;
    if (better) latest.set(k, a);
  }
  return [...latest.values()].sort((x, y) => y.updated - x.updated);
}

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

function AdminView({ adminKey }: { adminKey: string }) {
  const [data, err] = usePoll<Admin>(`/api/admin/${adminKey}`);
  const who = new URLSearchParams(window.location.search).get("who") ?? "";
  const apps = latestApps(data).filter((a) => !who || a.who.trim().toLowerCase() === who.trim().toLowerCase());
  const open = (a: App) => {
    window.location.href = `/admin/${adminKey}/app/${a.id}`;
  };
  return (
    <Shell adminKey={adminKey} data={data} who={who}>
      <div className="mb-6 flex flex-wrap items-baseline gap-4">
        <h1 className="text-3xl font-semibold">Apps</h1>
        {who && (
          <a href={`/admin/${adminKey}`} className="rounded-full bg-[#E3E5E8] px-3 py-0.5 text-sm">
            {who} ✕
          </a>
        )}
        <span className="text-[#4B5057]">{err ? `⚠ ${err}` : "Updates every 5 s"}</span>
      </div>
      {!data ? (
        <p className="text-[#4B5057]">{err || "Loading…"}</p>
      ) : (
        <Table className="text-base">
          <TableHeader>
            <TableRow>
              <TableHead>App</TableHead>
              <TableHead>Owner</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Updated</TableHead>
              <TableHead>Link</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {apps.length === 0 && (
              <TableRow>
                <TableCell colSpan={5} className="py-6 text-[#4B5057]">{who ? `No apps from ${who} yet.` : "No apps yet."}</TableCell>
              </TableRow>
            )}
            {apps.map((a) => (
              <TableRow key={a.id} onClick={() => open(a)} className="cursor-pointer">
                <TableCell className="max-w-[420px] whitespace-normal">
                  <div className="font-medium">{a.title}</div>
                  {a.status === "failed" && a.reason && <div className="text-[#4B5057] [overflow-wrap:anywhere]">{a.reason}</div>}
                </TableCell>
                <TableCell><Owner who={a.who} /></TableCell>
                <TableCell><StatusBadge status={a.status} /></TableCell>
                <TableCell className="text-[#4B5057]">{ago(a.updated)}</TableCell>
                <TableCell onClick={(e) => e.stopPropagation()}>
                  {a.status === "live" && a.url ? <OpenLink url={a.url} /> : null}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </Shell>
  );
}

type Full = App & { spec: string; versions: App[]; links?: Link[] };

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
  const [admin] = usePoll<Admin>(`/api/admin/${adminKey}`); // the shell's sidebar
  const [stopErr, setStopErr] = useState("");
  const stop = async () => {
    setStopErr("");
    const r = await fetch(`/api/admin/${adminKey}/app/${id}/stop`, { method: "POST" });
    if (!r.ok) setStopErr(((await r.json().catch(() => ({}))) as { error?: string }).error || `The server answered ${r.status}.`);
  };
  const history = [...(a?.versions ?? [])].sort((x, y) => y.created - x.created);
  return (
    <Shell adminKey={adminKey} data={admin} who="">
      <div>
        <div>
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
        </div>
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
                  <dd><Owner who={a.who} size={24} /></dd>
                  <dt className="text-[#4B5057]">Slot</dt>
                  <dd>{a.slot || "—"}</dd>
                  <dt className="text-[#4B5057]">Sandbox minutes</dt>
                  <dd>{a.minutes}</dd>
                  <dt className="text-[#4B5057]">Created</dt>
                  <dd>{when(a.created)}</dd>
                  <dt className="text-[#4B5057]">Golden</dt>
                  <dd>{a.golden ? `v${a.golden}` : "—"}</dd>
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
                {a.links?.length ? (
                  <div className="flex flex-col gap-2">
                    <h3 className="text-sm font-semibold uppercase tracking-wide text-[#4B5057]">Jump to</h3>
                    {a.links.map((l) => (
                      <JumpButton key={l.label} link={l} full />
                    ))}
                  </div>
                ) : null}
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
    </Shell>
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


// Monitoring (Marco, hq#782, 8:50 pm): Spend, Usage, Health. The figures are made up for the demo but fixed per app
// (seeded from its name), and built from the apps the admin page lists, so they always match the table.
const MONITOR_PAGES = [
  { page: "spend", label: "Spend", icon: Wallet },
  { page: "usage", label: "Usage", icon: Activity },
  { page: "health", label: "Health", icon: HeartPulse },
];
const BUDGET = 1500; // dollars a month for building apps, Claude and cloud together
const PER_M_TOKENS = 9; // blended dollars per million Claude tokens

function seed(key: string, n: number) {
  let h = 2166136261;
  for (const c of `${key}:${n}`) h = Math.imul(h ^ c.charCodeAt(0), 16777619);
  return ((h >>> 0) % 10000) / 10000;
}

type Figures = { a: App; claude: number; cloud: number; tokens: number; users: number; lastOpenDays: number; uptime: number; errors: number; errorWhy: string; live: boolean };

// po on #51: one app with a believable problem, everything else healthy (Marco's own apps clean)
const HEALTH_ISSUES: Record<string, { uptime: number; errors: number; why: string }> = {
  "deal-flow-tracker": { uptime: 99.1, errors: 4, why: "Timeouts loading the pipeline page" },
};

function figures(a: App): Figures {
  const k = `${a.who.trim().toLowerCase()}/${a.app}`;
  const live = a.status === "live";
  const claude = Math.round(38 + seed(k, 1) * 90 + a.changes * 22);
  const cloud = live ? Math.round(6 + seed(k, 2) * 14) : Math.round(1 + seed(k, 2) * 3);
  const ageDays = Math.max(0, (Date.now() / 1000 - a.created) / 86400);
  const fresh = ageDays < 1;
  const users = !live ? 0 : fresh ? 1 + Math.floor(seed(k, 3) * 2) : 3 + Math.floor(seed(k, 3) * 12);
  // only a stopped app gets the "not opened lately" figure, and never longer ago than the app is old (qa on #51)
  const lastOpenDays =
    a.status === "stopped" ? Math.min(9 + Math.floor(seed(k, 4) * 12), Math.floor(ageDays)) : live && !fresh ? Math.floor(seed(k, 4) * 2) : 0;
  const issue = live ? HEALTH_ISSUES[a.app] : undefined;
  const uptime = !live ? 0 : issue ? issue.uptime : fresh ? 100 : 99.9 + Math.round(seed(k, 5) * 9) / 100;
  return { a, claude, cloud, tokens: (claude / PER_M_TOKENS) * 1e6, users, lastOpenDays, uptime, errors: issue?.errors ?? 0, errorWhy: issue?.why ?? "", live };
}

const usd = (n: number) => `$${Math.round(n).toLocaleString("en-US")}`;
const mtok = (n: number) => `${(n / 1e6).toFixed(1)}M`;

function Stat({ label, value, sub }: { label: string; value: string; sub?: React.ReactNode }) {
  return (
    <Card className="gap-1 py-5">
      <CardHeader className="px-5">
        <CardTitle className="text-sm font-medium text-[#4B5057]">{label}</CardTitle>
      </CardHeader>
      <CardContent className="px-5">
        <div className="text-3xl font-semibold tabular-nums">{value}</div>
        {sub && <div className="mt-1 text-sm text-[#4B5057]">{sub}</div>}
      </CardContent>
    </Card>
  );
}

function MonitoringView({ adminKey, page }: { adminKey: string; page: string }) {
  const [data, err] = usePoll<Admin>(`/api/admin/${adminKey}`);
  const all = latestApps(data).map(figures);
  const title = MONITOR_PAGES.find((m) => m.page === page)?.label ?? "Monitoring";
  const month = new Date().toLocaleString("en-US", { month: "long" });
  const open = (a: App) => {
    window.location.href = `/admin/${adminKey}/app/${a.id}`;
  };
  let body: React.ReactNode;
  if (!data) body = <p className="text-[#4B5057]">{err || "Loading…"}</p>;
  else if (page === "spend") {
    const claude = all.reduce((t, f) => t + f.claude, 0);
    const cloud = all.reduce((t, f) => t + f.cloud, 0);
    const total = claude + cloud;
    const pct = Math.min(100, Math.round((total / BUDGET) * 100));
    const byPerson = new Map<string, { who: string; apps: number; claude: number; cloud: number }>();
    for (const f of all) {
      const k = f.a.who.trim().toLowerCase();
      const p = byPerson.get(k) ?? { who: f.a.who, apps: 0, claude: 0, cloud: 0 };
      byPerson.set(k, { ...p, apps: p.apps + 1, claude: p.claude + f.claude, cloud: p.cloud + f.cloud });
    }
    const people = [...byPerson.values()].sort((x, y) => y.claude + y.cloud - (x.claude + x.cloud));
    body = (
      <div className="flex flex-col gap-8">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <Stat label="Claude tokens" value={usd(claude)} sub={`${mtok(all.reduce((t, f) => t + f.tokens, 0))} tokens`} />
          <Stat label="Cloud" value={usd(cloud)} sub="App servers, deploys, logs" />
          <Stat
            label={`Total vs ${usd(BUDGET)} budget`}
            value={usd(total)}
            sub={
              <div className="flex items-center gap-2">
                <div className="h-2 flex-1 rounded-full bg-[#E3E5E8]">
                  <div className="h-2 rounded-full bg-[#007A33]" style={{ width: `${pct}%` }} />
                </div>
                <span className="tabular-nums">{pct}%</span>
              </div>
            }
          />
        </div>
        <section>
          <h2 className="mb-2 text-xl font-semibold">By person</h2>
          <Table className="text-base">
            <TableHeader>
              <TableRow>
                <TableHead>Person</TableHead>
                <TableHead className="text-right">Apps</TableHead>
                <TableHead className="text-right">Claude</TableHead>
                <TableHead className="text-right">Cloud</TableHead>
                <TableHead className="text-right">Total</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {people.map((p) => (
                <TableRow key={p.who}>
                  <TableCell><Owner who={p.who} /></TableCell>
                  <TableCell className="text-right tabular-nums">{p.apps}</TableCell>
                  <TableCell className="text-right tabular-nums">{usd(p.claude)}</TableCell>
                  <TableCell className="text-right tabular-nums">{usd(p.cloud)}</TableCell>
                  <TableCell className="text-right font-medium tabular-nums">{usd(p.claude + p.cloud)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </section>
        <section>
          <h2 className="mb-2 text-xl font-semibold">By app</h2>
          <Table className="text-base">
            <TableHeader>
              <TableRow>
                <TableHead>App</TableHead>
                <TableHead>Owner</TableHead>
                <TableHead className="text-right">Claude</TableHead>
                <TableHead className="text-right">Cloud</TableHead>
                <TableHead className="text-right">Total</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {[...all].sort((x, y) => y.claude + y.cloud - (x.claude + x.cloud)).map((f) => (
                <TableRow key={f.a.id} className="cursor-pointer hover:bg-[#F7F8F9]" onClick={() => open(f.a)}>
                  <TableCell className="font-medium">{f.a.title}</TableCell>
                  <TableCell><Owner who={f.a.who} /></TableCell>
                  <TableCell className="text-right tabular-nums">{usd(f.claude)}</TableCell>
                  <TableCell className="text-right tabular-nums">{usd(f.cloud)}</TableCell>
                  <TableCell className="text-right font-medium tabular-nums">{usd(f.claude + f.cloud)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </section>
      </div>
    );
  } else if (page === "usage") {
    const rows = [...all].sort((x, y) => x.lastOpenDays - y.lastOpenDays || y.users - x.users);
    body = (
      <Table className="text-base">
        <TableHeader>
          <TableRow>
            <TableHead>App</TableHead>
            <TableHead>Owner</TableHead>
            <TableHead className="text-right">Active users (7 days)</TableHead>
            <TableHead>Last opened</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((f) => {
            const notYet = !f.live && f.a.status !== "stopped";
            const idle = f.a.status === "stopped" && f.lastOpenDays >= 7;
            return (
              <TableRow key={f.a.id} className="cursor-pointer hover:bg-[#F7F8F9]" onClick={() => open(f.a)}>
                <TableCell className="font-medium">{f.a.title}</TableCell>
                <TableCell><Owner who={f.a.who} /></TableCell>
                <TableCell className="text-right tabular-nums">{notYet ? "—" : `${f.users} of 50`}</TableCell>
                <TableCell>
                  {notYet ? (
                    <span className="text-[#4B5057]">Not live yet</span>
                  ) : idle ? (
                    <Badge className="h-6 px-2.5 text-sm bg-[#FEF3F2] text-[#B42318]">Not opened in {f.lastOpenDays} days</Badge>
                  ) : f.lastOpenDays === 0 ? (
                    "Today"
                  ) : f.lastOpenDays === 1 ? (
                    "Yesterday"
                  ) : (
                    `${f.lastOpenDays} days ago`
                  )}
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    );
  } else {
    body = (
      <Table className="text-base">
        <TableHeader>
          <TableRow>
            <TableHead>App</TableHead>
            <TableHead>Owner</TableHead>
            <TableHead>Status</TableHead>
            <TableHead className="text-right">Uptime (30 days)</TableHead>
            <TableHead className="text-right">Errors (24 h)</TableHead>
            <TableHead>Last error</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {[...all].sort((x, y) => y.errors - x.errors).map((f) => (
            <TableRow key={f.a.id} className="cursor-pointer hover:bg-[#F7F8F9]" onClick={() => open(f.a)}>
              <TableCell className="font-medium">{f.a.title}</TableCell>
              <TableCell><Owner who={f.a.who} /></TableCell>
              <TableCell><StatusBadge status={f.a.status} /></TableCell>
              <TableCell className="text-right tabular-nums">{f.live ? `${f.uptime.toFixed(2)}%` : "—"}</TableCell>
              <TableCell className={`text-right tabular-nums ${f.errors >= 3 ? "font-medium text-[#B42318]" : ""}`}>{f.live ? f.errors : "—"}</TableCell>
              <TableCell className={f.errorWhy ? "text-[#B42318]" : "text-[#4B5057]"}>{f.errorWhy || "—"}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    );
  }
  return (
    <Shell adminKey={adminKey} data={data} who="">
      <div className="mb-6 flex flex-wrap items-baseline gap-4">
        <h1 className="text-3xl font-semibold">{title}</h1>
        <span className="text-[#4B5057]">{err ? `⚠ ${err}` : page === "spend" ? `${month} so far` : "Every app the company's people built"}</span>
      </div>
      {body}
    </Shell>
  );
}

export default function App() {
  const [, kind, arg, sub, id] = window.location.pathname.split("/");
  if (kind === "admin" && arg && sub === "app" && id) return <DetailView adminKey={arg} id={id} />;
  if (kind === "admin" && arg && sub === "monitoring" && id) return <MonitoringView adminKey={arg} page={id} />;
  if (kind === "admin" && arg) return <AdminView adminKey={arg} />;
  if (kind === "status" && arg) return <StatusView id={arg} />;
  return <p className="p-10">Not found.</p>;
}
