---
name: "playwright"
description: "Use when the task requires automating a real browser from the terminal (navigation, form filling, snapshots, screenshots, data extraction, UI-flow debugging) via `playwright-cli` or the bundled wrapper script."
---


# Playwright CLI Skill

Drive a real browser from the terminal using `playwright-cli`. Prefer the bundled wrapper script so the CLI works even when it is not globally installed.
Treat this skill as CLI-first automation. Do not pivot to `@playwright/test` unless the user explicitly asks for test files.

## Prerequisite check (required)

Before proposing commands, check whether `npx` is available (the wrapper depends on it):

```bash
command -v npx >/dev/null 2>&1
```

If it is not available, pause and ask the user to install Node.js/npm (which provides `npx`). Provide these steps verbatim:

```bash
# Verify Node/npm are installed
node --version
npm --version

# If missing, install Node.js/npm, then:
npm install -g @playwright/cli@latest
playwright-cli --help
```

Once `npx` is present, proceed with the wrapper script. A global install of `playwright-cli` is optional.


## This Machine: First-Try Rules

This WSL machine has a few repeat failure modes. Apply these before choosing a command.

### Chromium Launch

For browser automation launched from Codex tools, run Chromium outside the sandbox when the task needs a real browser, screenshots, canvas pixels, or headed mode. Inside the sandbox Chromium can fail with:

```text
sandbox_host_linux.cc:41 Check failed: shutdown: Operation not permitted
```

Use the installed Chromium path, not stale version-specific paths from old tests:

```text
/home/manh/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome
```

Preferred direct Node launch pattern for probes:

```bash
node --input-type=module -e 'import { chromium } from "playwright";
const browser = await chromium.launch({
  executablePath: "/home/manh/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome",
  headless: true,
  args: ["--no-sandbox", "--disable-dev-shm-usage"],
});
// ...work...
await browser.close();'
```

When invoking this through Codex, request escalation with `sandbox_permissions: "require_escalated"` on the first try. Suggested prefix rule: `["node", "--input-type=module"]`.

### Package Resolution

Do not run a Node script from `/home/manh/.codex/skills/...` that imports `playwright` unless that skill folder has its own `node_modules`. Node resolves ESM packages relative to the script file path, not the repo `cwd`, so this commonly fails with:

```text
ERR_MODULE_NOT_FOUND: Cannot find package 'playwright' imported from /home/manh/.codex/skills/...
```

First-choice workaround: use inline `node --input-type=module -e 'import { chromium } from "playwright"; ...'` from the target repo. If the repo lacks `playwright`, install it transiently without touching package metadata:

```bash
npm install --no-save --no-package-lock playwright
```

Avoid `npx -p playwright node /home/manh/.codex/skills/.../script.js`; it still resolves imports from the external script path and can fail.

### Phaser / Canvas Screenshots

For Phaser, WebGL, or canvas-heavy pages on this machine, headless WebGL screenshots can be black or hang during `ReadPixels`. Use a canvas-renderer probe by adding GPU-disabling args:

```text
--disable-gpu --disable-software-rasterizer
```

Reliable canvas screenshot pattern:

```bash
node --input-type=module -e 'import { chromium } from "playwright";
const browser = await chromium.launch({
  executablePath: "/home/manh/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome",
  headless: true,
  args: ["--no-sandbox", "--disable-gpu", "--disable-software-rasterizer"],
});
const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
await page.goto("http://127.0.0.1:3000/world", { waitUntil: "domcontentloaded" });
await page.waitForTimeout(3000);
await page.locator("canvas").first().screenshot({ path: "/tmp/world-canvas.png", timeout: 10000 });
await browser.close();'
```

For measurements, prefer `page.evaluate` over screenshots. Record both world/CSS pixels and `window.devicePixelRatio`. For mobile checks, use `devices["iPhone 14 Pro Max"]` and expect CSS pixels such as `430 x 740` with DPR `3`.

### Server Checks

Before probing a local app, verify the dev server is actually listening. If `page.goto` returns `ERR_CONNECTION_REFUSED`, start or restart the dev server first. For this repo, use:

```bash
npm run dev
```

Do not assume a server from a previous interrupted turn is still alive.

## Skill path (set once)

```bash
export CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
export PWCLI="$CODEX_HOME/skills/playwright/scripts/playwright_cli.sh"
```

User-scoped skills install under `$CODEX_HOME/skills` (default: `~/.codex/skills`).

## Quick start

Use the wrapper script:

```bash
"$PWCLI" open https://playwright.dev --headed
"$PWCLI" snapshot
"$PWCLI" click e15
"$PWCLI" type "Playwright"
"$PWCLI" press Enter
"$PWCLI" screenshot
```

If the user prefers a global install, this is also valid:

```bash
npm install -g @playwright/cli@latest
playwright-cli --help
```

## Core workflow

1. Open the page.
2. Snapshot to get stable element refs.
3. Interact using refs from the latest snapshot.
4. Re-snapshot after navigation or significant DOM changes.
5. Capture artifacts (screenshot, pdf, traces) when useful.

Minimal loop:

```bash
"$PWCLI" open https://example.com
"$PWCLI" snapshot
"$PWCLI" click e3
"$PWCLI" snapshot
```

## When to snapshot again

Snapshot again after:

- navigation
- clicking elements that change the UI substantially
- opening/closing modals or menus
- tab switches

Refs can go stale. When a command fails due to a missing ref, snapshot again.

## Recommended patterns

### Form fill and submit

```bash
"$PWCLI" open https://example.com/form
"$PWCLI" snapshot
"$PWCLI" fill e1 "user@example.com"
"$PWCLI" fill e2 "password123"
"$PWCLI" click e3
"$PWCLI" snapshot
```

### Debug a UI flow with traces

```bash
"$PWCLI" open https://example.com --headed
"$PWCLI" tracing-start
# ...interactions...
"$PWCLI" tracing-stop
```

### Multi-tab work

```bash
"$PWCLI" tab-new https://example.com
"$PWCLI" tab-list
"$PWCLI" tab-select 0
"$PWCLI" snapshot
```

## Wrapper script

The wrapper script uses `npx --package @playwright/cli playwright-cli` so the CLI can run without a global install:

```bash
"$PWCLI" --help
```

Prefer the wrapper unless the repository already standardizes on a global install.

## References

Open only what you need:

- CLI command reference: `references/cli.md`
- Practical workflows and troubleshooting: `references/workflows.md`

## Guardrails

- Always snapshot before referencing element ids like `e12`.
- Re-snapshot when refs seem stale.
- Prefer explicit commands over `eval` and `run-code` unless needed.
- When you do not have a fresh snapshot, use placeholder refs like `eX` and say why; do not bypass refs with `run-code`.
- Use `--headed` when a visual check will help.
- When capturing artifacts in this repo, use `output/playwright/` and avoid introducing new top-level artifact folders.
- Default to CLI commands and workflows, not Playwright test specs.
