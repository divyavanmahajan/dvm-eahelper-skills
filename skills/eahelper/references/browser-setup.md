# Browser Setup Reference (Windows + macOS)

`eahelper proxy` authenticates by attaching over Chrome DevTools Protocol (CDP) to a browser
window that is **already logged in** to LeanIX, and reading the Bearer token off an outbound
network request. This requires the browser to be started with `--remote-debugging-port=9222`.

## Why you can't just add the flag to your normal browser

If Edge or Chrome is already running, launching a "new window" with
`--remote-debugging-port=9222` does **nothing** — existing browser processes silently ignore the
flag on subsequent launches. The port never opens, and the proxy fails to connect.

The fix is always the same: launch a **separate, isolated instance** with its own
`--user-data-dir`, distinct from your normal profile. This creates a second, independent browser
process that respects the debugging flag.

## Windows (PowerShell)

### Edge (recommended — preinstalled on Windows)

```powershell
Start-Process "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" `
  "--remote-debugging-port=9222 --user-data-dir=C:\Temp\edge-debug --no-first-run --no-default-browser-check"
```

### Chrome

```powershell
Start-Process "C:\Program Files\Google\Chrome\Application\chrome.exe" `
  "--remote-debugging-port=9222 --user-data-dir=C:\Temp\chrome-debug --no-first-run"
```

### Verify the port is open

```powershell
Invoke-RestMethod http://localhost:9222/json/version
```

Expect a JSON body with browser/version fields. A connection error means the browser did not
actually start with the debug port — see Troubleshooting below.

## macOS (bash/zsh)

### Chrome

```bash
open -na "Google Chrome" --args --remote-debugging-port=9222 --user-data-dir="$HOME/chrome-debug"
```

### Edge

```bash
open -na "Microsoft Edge" --args --remote-debugging-port=9222 --user-data-dir="$HOME/edge-debug"
```

`open -na` always forces a new process instance, which is why (unlike double-clicking the Dock
icon) this reliably launches a second, isolated browser even if the app is already open.

### Verify the port is open

```bash
curl -s http://localhost:9222/json/version
```

Expect JSON output with browser/version fields.

## After the debug browser is open

1. In the new browser window (not your normal one), navigate to your LeanIX workspace URL.
2. Log in normally.
3. Navigate around a little (e.g. open the Inventory) so at least one authenticated GraphQL/API
   request fires — the proxy needs to observe a real request to capture the Authorization header.
4. Leave this window open for the duration of your `eahelper proxy` session.
5. In a separate terminal, run `eahelper proxy`.

## Skipping the browser entirely — Technical User API key

For automation, CI, or headless environments, you can skip browser/CDP entirely by using a LeanIX
Technical User API key:

1. In LeanIX: **Administration → Technical Users → Create Technical User**, assign roles, copy the
   generated API key (shown once).
2. Pass it to the proxy:

```bash
eahelper proxy --api-token "your-api-key-here"
# or
export LEANIX_API_TOKEN="your-api-key-here"     # macOS/Linux
eahelper proxy
```

```powershell
$env:LEANIX_API_TOKEN = "your-api-key-here"      # Windows
eahelper proxy
```

The proxy exchanges the key for a Bearer token via OAuth2 client-credentials at startup, and
automatically re-exchanges it whenever the token expires — no browser needed at all.

## Notes on user-data-dir paths

- Any writable directory works; the examples above (`C:\Temp\edge-debug`,
  `~/chrome-debug`) are just conventions. Keep it separate from your default profile.
- The directory is created automatically if it doesn't exist.
- Re-using the same debug directory across sessions preserves cookies/login — you may not need to
  log in again on subsequent runs, as long as the browser was closed cleanly.
