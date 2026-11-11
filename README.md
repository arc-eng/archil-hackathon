# Golden Sandbox

**Anyone in the company can build an app with Claude. The company owns every app.**

A head of engineering found out by chance that an employee had spent $3,000 in tokens in one day building their own
CRM. It lived on their laptop, and nobody knew. People will build their own tools with AI either way; Golden Sandbox
lets them, inside the company's guard rails, where the company can see what exists, what it costs and where the data
lives.

- 🎞️ [The slide](https://golden-sandbox-42301619537.us-west1.run.app/how)
- 🏗️ [The architecture](https://golden-sandbox-42301619537.us-west1.run.app/architecture)
- ▶️ [The 1-minute video](https://golden-sandbox-42301619537.us-west1.run.app/video)

## How it works

- **Claude interviews first.** An employee asks for an app in their Claude app. Claude acts as the product owner:
  asks who it's for, what it keeps and when it's done, plays the spec back, and only then sends it on.
- **Claude Code builds it in the employee's own Archil sandbox.** Each person gets a persistent sandbox, copied once
  from the company's **golden sandbox**: its skills, design system, house rules and policies. Their earlier apps and
  history are still there next time.
- **No cloud keys in the sandbox.** It can build and test the app, but it can't deploy anything or reach company systems.
- **Only the company's builder deploys.** It picks up the built code and deploys it to the company's own cloud
  (Cloud Run), under an account that may only create app services. Each app runs with no permissions of its own.
- **Requests that send company data outside are refused** (a personal Dropbox, personal email, outside webhooks).
- **The admin sees every app**: who built it, its status and link, spend, usage and health (sample figures in this demo), and can stop any app.

## Run it

You need an [Archil](https://docs.archil.com/getting-started/introduction) account, a Claude Code token and a Google Cloud project with Cloud Run and
Cloud Build.

```bash
cp .env.example .env    # then fill in the values below
uv run builder.py golden            # create the golden sandbox
uv run builder.py publish           # publish golden/ as its first version
uv run connector.py                 # the MCP connector and the web pages
```

| Env | What |
|---|---|
| `ARCHIL_API_KEY`, `ARCHIL_REGION` | Archil |
| `CLAUDE_CODE_OAUTH_TOKEN` | Claude Code token, passed to each sandbox command, never written to disk |
| `CONNECTOR_PATH_SECRET` | secret part of the connector's address (32+ characters); the admin page's address derives from it |
| `GCP_PROJECT` | the Google Cloud project apps deploy to |
| `PUBLIC_URL` | optional: the connector's public address, for status links |

Add the connector to Claude as a custom connector at `<PUBLIC_URL>/mcp/<CONNECTOR_PATH_SECRET>`. Tests: `uv run pytest`.

## Files

| Path | What |
|---|---|
| `connector.py` | MCP server (`request_app`, `my_apps`, `stop_app`) plus the status, admin, slide and architecture pages |
| `service.py` | spec checks, the outside-data rule, background build then deploy |
| `builder.py` | golden sandbox, one sandbox per employee, the Claude Code build and its checks |
| `golden/` | the golden image as code: setup, house rules (`claude/CLAUDE.md`), company skills, app template |
| `golden.py` | publishes `golden/` as version N; each request syncs the latest version into the person's sandbox |
| `registry.py` | every request and app, kept on an Archil disk |
| `deploy.py` | Cloud Build deploys a built app to its Cloud Run service |
| `web/` | the admin page (React), the slide, the architecture page and the video |
