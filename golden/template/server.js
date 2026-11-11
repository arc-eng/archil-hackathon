// Company app template. Plain Node, no dependencies. Listens on $PORT (Cloud Run sets it).
// Data lives in DATA_FILE as JSON (resets when the app restarts: fine for a demo app).
const http = require("node:http");
const fs = require("node:fs");
const path = require("node:path");

const PORT = Number(process.env.PORT || 8080);
const DATA_FILE = process.env.DATA_FILE || path.join(__dirname, "data.json");
const PUBLIC = path.join(__dirname, "public");
const TYPES = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css", ".json": "application/json", ".svg": "image/svg+xml" };

function load() {
  try { return JSON.parse(fs.readFileSync(DATA_FILE, "utf8")); } catch { return { items: [] }; }
}
function save(data) { fs.writeFileSync(DATA_FILE, JSON.stringify(data, null, 2)); }
function send(res, code, body, type = "application/json") {
  res.writeHead(code, { "content-type": type });
  res.end(typeof body === "string" || Buffer.isBuffer(body) ? body : JSON.stringify(body));
}
function readBody(req) {
  return new Promise((resolve, reject) => {
    let s = "";
    req.on("data", (c) => { s += c; if (s.length > 1e6) reject(new Error("too big")); });
    req.on("end", () => { try { resolve(s ? JSON.parse(s) : {}); } catch (e) { reject(e); } });
  });
}

// --- API: add your routes here -------------------------------------------------
const routes = {
  "GET /health": async () => [200, { ok: true }],
  "GET /api/items": async () => [200, load().items],
  "POST /api/items": async (req) => {
    const body = await readBody(req);
    const data = load();
    const item = { id: Date.now().toString(36), ...body, createdAt: new Date().toISOString() };
    data.items.push(item);
    save(data);
    return [201, item];
  },
};
// -------------------------------------------------------------------------------

http.createServer(async (req, res) => {
  const url = new URL(req.url, "http://x");
  const handler = routes[`${req.method} ${url.pathname}`];
  try {
    if (handler) { const [code, body] = await handler(req, url); return send(res, code, body); }
    if (req.method !== "GET") return send(res, 404, { error: "not found" });
    const file = path.join(PUBLIC, url.pathname === "/" ? "index.html" : url.pathname);
    if (!file.startsWith(PUBLIC) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) return send(res, 404, { error: "not found" });
    send(res, 200, fs.readFileSync(file), TYPES[path.extname(file)] || "application/octet-stream");
  } catch (e) {
    send(res, 400, { error: String(e.message || e) });
  }
}).listen(PORT, () => console.log(`listening on ${PORT}`));
