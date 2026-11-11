// A stopped app's slot: one plain page.
require("node:http").createServer((req, res) => {
  if (req.url === "/health") { res.writeHead(200, { "content-type": "application/json" }); return res.end('{"ok":true}'); }
  res.writeHead(410, { "content-type": "text/html; charset=utf-8" });
  res.end("<!doctype html><meta name=viewport content='width=device-width'><title>Stopped</title><p style='font:16px system-ui;margin:3em'>This app was stopped by its owner.</p>");
}).listen(Number(process.env.PORT || 8080));
