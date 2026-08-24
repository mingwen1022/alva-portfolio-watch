# Alva platform build contract

What the platform requires to get a Playbook built, running, and pushing to a phone.
Platform constraints only — signal definitions live in `signal-spec.md`, data fields in
`data-contract.md`.

## Runtime

Scripts execute in the **Alva V8 runtime**.

- **JavaScript only.** No Python, no shell.
- **No top-level `await`.** Wrap everything in an async function and call it.
- **`require()`, not `import`.**

| require | Purpose | Signature that actually works |
|---|---|---|
| `net/http` | HTTP | `http.fetch(url, { headers })` |
| `secret-manager` | Credentials | `secret.loadPlaintext("ARRAYS_JWT")` — **not** `getSecret()` |
| `alfs` | Filesystem | `readFile` / `writeFile`, absolute paths only |
| `env` | Cronjob arguments | `require("env").args` |
| `@alva/feed` | Feed SDK | `Feed` · `feedPath` · `makeDoc` · `alertOutput` · `str` · `num` · `messagePresentationField` |
| `@alva/alvaask` | LLM | `ask(user, { system })` |
| `./x.js` | Sibling script | Relative require works; upload the scripts into the same directory |

**`feed.run()` swallows exceptions.** A script that throws still reports the cronjob as
`completed` with empty logs. Judge a run by its artifacts — file `mod_time`, whether the
fields changed — never by its status.

**Cron expressions are evaluated in UTC.** Convert pre-market and post-close times from
ET, and account for daylight saving: a hardcoded UTC constant is wrong for half the year.

## Filesystem (ALFS)

```
/alva/home/<username>/playbooks/<name>/data/portfolio.json   absolute      OK
~/playbooks/<name>/data/portfolio.json                        home-relative OK
playbooks/<name>/data/portfolio.json                          INVALID_ARGUMENT
/playbooks/<name>/data/portfolio.json                         NOT_FOUND
```

`alva whoami` returns `username` and `home_path`. Build every path from it; never ask the
user to type one.

```bash
alva fs write   --path <abs> --file <local>
alva fs read    --path <abs>
alva fs stat    --path <abs>     # mod_time — use it to prove a run actually wrote
alva fs readdir --path <abs>
alva fs remove  --path <abs>
```

**Read back and diff after every upload.** A wrong path form returns 404 rather than
raising, so a failed upload looks like a successful one. The diff costs nothing.

## Reading data from the page

**A published page sits behind the gateway, where relative-path `fetch` always 404s.**
Use the `@alva-ai/toolkit` ALFS client with absolute paths.

```html
<script src="https://unpkg.com/@alva-ai/toolkit/dist/browser.global.js"></script>
```

```js
const client = new AlvaToolkit.AlvaClient({});      // platform injects credentials
const portfolio = await client.fs.read({
  path: `${ALFS_ROOT}/data/portfolio.json` });      // ALFS_ROOT is one constant
```

Keep the root in a **single constant**: empty for local preview (relative paths against a
static server), the ALFS root when published. One HTML file then runs in both places —
do not maintain two versions.

**A published page cannot be opened by typing its URL.** The gateway answers
`PLAYBOOK_PAGE_NAVIGATION_DENIED`; it has to be opened from inside the Alva app.
`curl -L` against the URL does return the HTML, which is enough to verify content.

## Cronjob, feed, playbook

```
cronjob    runs one ALFS script on a schedule        alva deploy create
   |  one-to-one
feed       the cronjob's public identity; alerts leave through it
   |  many-to-one
playbook   the page plus the feeds attached to it    alva release playbook --feeds
```

**Group cronjobs by cadence, not one per signal.** Signals that share a cadence share a
script: one less job is one less failure point and one less duplicate fetch. Signals with
different cadences must stay apart — what makes them different is when their data changes.

```bash
alva deploy create  --name <n> --path <alfs-script> --cron "<expr>" --push-notify \
                    --args '{"root":"/alva/home/<user>/playbooks/<name>",
                             "playbookUrl":"<published page URL>"}'
alva deploy trigger --id <id>          # fires immediately; really does deliver alerts
alva deploy get     --id <id>
alva deploy runs    --id <id>
alva deploy run-logs --id <id> --run-id <n>
```

**`--args` is not optional for the producers in this skill.** They read `root` (the
playbook's absolute ALFS path) and `playbookUrl` (the link at the bottom of every push) from
`require("env").args`. Omit `--args` and every run throws — and because `feed.run()` swallows
exceptions, all three cronjobs report `completed` with empty logs while nothing is written.

**Verify the first run by its artifacts, not its status:** `alva deploy trigger --id <id>`,
then `alva fs stat --path <root>/data/findings.json` and check `mod_time` moved.

**Initialization is not a cron.** Baselines are built once; the cronjobs only do increments.

**When several producers write the same `findings.json`, each replaces only its own
signals.** A wholesale overwrite deletes what another producer just wrote, and the symptom
is "no alerts today" — which reads as a quiet market.

## Push requires three things at once

Miss any one and the page still works, alerts never reach the phone, and nothing errors.

1. The script declares an alert output via `alertOutput()`.
2. The TypeDoc has a **`body` string field at the root**. That is what the push shows.
3. The run was started by **the cronjob bound to that feed**. A manual `alva run` never pushes.

**`notify/message` is a reserved group name** — do not use it for your own output group.

Subscription is separate:

```bash
alva alert enable          # target must be a feed (automation), never a playbook
```

**This is the step most often missed.** Every other step leaves an artifact behind; this
one does not, so nothing looks wrong when it is skipped.

## Release order

| # | Command | What breaks if skipped |
|---|---|---|
| 1 | `alva whoami` | Every path is wrong |
| 2 | `alva deploy create` ×N | Nothing is scheduled |
| 3 | `alva release feed --name --version --cronjob-id` | The cronjob has no public identity, so no alerts |
| 4 | `alva alert enable` | Page works, nothing ever pushes |
| 5 | `alva fs write` for `data/`, `config/`, `index.html`, `README.md` | Blank page |
| 6 | `alva lint playbook <path>` | An error-level finding blocks the release |
| 7 | `alva release playbook-draft` | An unreviewed page goes straight to the user |
| 8 | `alva release playbook --name --version --feeds --readme-url <abs>` | — |

```
--feeds       '[{"feed_id":123,"feed_major":1}, ...]'
--version     semver; re-publishing the same name must increment or the platform rejects it
--readme-url  an absolute ALFS path — not a local path and not a URL
```

**Confirm every signature with `alva <command> --help`.** The CLI changes; `--help` does not
go stale. The shapes above are orientation, not a substitute.

## Design gate

```bash
alva lint playbook <path/to/index.html>        # positional argument, not --path
```

**Error-level findings really do block publishing.** Run it locally — far cheaper than
discovering it at the release step.

Design system: `https://alva-ai-static.b-cdn.net/design-system/v1/design-system.css`

- **Font weight is restricted to 400 and 500.** 600 is an error-level finding.
- **Scrolling happens on `body`.** `html` is `height:100%; overflow:hidden`, so
  `window.scrollTo` and `documentElement.scrollHeight` silently do nothing.
- **`.widget-grid` is an 8-column grid** and `.col-N` must be its direct child.

## Billing

Check before assuming. Endpoint pricing changes — several endpoints in this project were
documented as free and later turned out to be billed.

```bash
alva credits wallet              # balance
alva credits items --today       # itemized; the command itself is free
```

**One logical call produces several billing rows.** An `ask()` with search emits one large
rollup row (empty `extras`) plus a handful of 1–5 credit search rows. **Dividing the total
by the row count yields a number that corresponds to nothing** — sort by `createdAtMs`,
identify the rollup rows, and count those.

**Billing lags by minutes.** Checking the balance right after a run and seeing no change
is a false negative. Wait, then read the itemized list.

**`alva run` always reports `credits_used: 0`,** even for runs that were billed.

## Failures that produce no error

Each of these happened in this project.

| Symptom | Cause | How to detect |
|---|---|---|
| Every fetch on the page 404s | Relative paths behind the gateway | See "Reading data from the page" |
| Cronjob `completed`, logs empty, artifacts unchanged | Script threw; `feed.run` swallowed it | Check file `mod_time` |
| Alerts never push | One of the three push requirements is missing | Check all three |
| Upload succeeds but reads back empty | Wrong ALFS path form | Diff after writing |
| One symbol quietly disappears | The holdings list is duplicated across files and one copy was missed | Keep one list; reference it everywhere |
| A field renders as a dash | A field whitelist in a mapping layer silently dropped it | Spread (`{...x}`), never enumerate |
| An intraday alert is timestamped after the run that produced it | A 24-hour market's bar extends to fetch time while `asOf` is pinned to a close | Assert every timestamp ≤ `generatedAt` |
| Every reference in the installed package is a dead link | Skills install as directories; symlinks copied out are broken links | Resolve symlinks at package time and verify no symlink remains |
