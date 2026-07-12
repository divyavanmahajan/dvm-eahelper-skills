# Browser Setup Reference (Windows + macOS)

`eahelper server` authenticates by attaching over Chrome DevTools Protocol (CDP) to a browser
window that is logged in to LeanIX, and reading the Bearer token off an outbound network request.
As of v0.2.0, this browser is **managed by eahelper itself** — you normally do not launch it by
hand.

## Default story: the managed browser

When `eahelper server` needs a token (first run, or after the saved token expires and can't be
silently refreshed), it:

1. Launches an isolated browser instance itself, with its own profile directory at
   `~/.eahelper/browser-profile` (persistent across runs — SSO cookies survive, so you typically
   only need to log in once, ever, per machine).
2. Opens it with `--remote-debugging-port=19222` (the CDP port `eahelper` uses; not the `9222`
   convention from older manual-setup guides).
3. Navigates to your configured workspace URL and waits for you to log in.
4. Watches for a real authenticated GraphQL/API request to capture the Authorization header.
5. **Closes the browser window automatically** once the token is captured — you don't need to
   remember to close it, and it won't sit there consuming resources between runs.

You don't need to do anything except log in when the window appears. Nothing to launch, nothing to
leave open.

### Overriding the default behavior

- Keep the browser open after capture (e.g. for manual poking-around, or slow SSO redirects that
  need more time to settle): pass `--keep-browser` to `eahelper server`, or set it once via
  `eahelper config set browser.keep_open true`.
- Use a specific browser: `eahelper server --browser chrome` or `--browser edge`.
- Use a different CDP port (e.g. `19222` is already taken by something else):
  `eahelper server --cdp-port 19333`, or `eahelper config set browser.cdp_port 19333`.

## Windows: Chrome vs. Edge

**Chrome is now the preferred managed browser on Windows.** Edge's CDP support requires **every**
Edge window on the machine to be closed first — a running Edge instance (even a background one
kept alive by "continue running apps in the background" settings) silently ignores the CDP flag on
a new window, exactly like the manual-launch problem described below. If `eahelper` detects Edge is
the target and other Edge windows are open, it warns you and asks you to close them before
proceeding. When in doubt, install/use Chrome instead — it doesn't have this restriction.

## Why manual `--remote-debugging-port` launches used to be needed

Older versions of this workflow required you to hand-launch a debug browser yourself. That's no
longer the primary path — `eahelper server` does it for you — but the underlying constraint still
matters if you use the manual fallback below: if Edge or Chrome is already running, launching a
"new window" with `--remote-debugging-port` does **nothing** — existing browser processes silently
ignore the flag on subsequent launches. The fix is always the same: launch a **separate, isolated
instance** with its own `--user-data-dir`, distinct from your normal profile.

## Manual fallback (only if the managed browser doesn't work for your environment)

Use this if the managed browser fails to launch (e.g. locked-down corporate imaging, no permission
to spawn processes) or you explicitly want a manually-controlled session. Pass `--token` to
`eahelper server` once you've extracted a token another way, or point `--connect`/`--cdp-port` at
your manually-launched instance.

### Windows (PowerShell)

**Chrome (recommended):**

```powershell
Start-Process "C:\Program Files\Google\Chrome\Application\chrome.exe" `
  "--remote-debugging-port=19222 --user-data-dir=C:\Temp\chrome-debug --no-first-run"
```

**Edge (close ALL Edge windows first):**

```powershell
Start-Process "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" `
  "--remote-debugging-port=19222 --user-data-dir=C:\Temp\edge-debug --no-first-run --no-default-browser-check"
```

### Verify the port is open

```powershell
Invoke-RestMethod http://localhost:19222/json/version
```

Expect a JSON body with browser/version fields. A connection error means the browser did not
actually start with the debug port — see [troubleshooting.md](troubleshooting.md).

## macOS (bash/zsh)

### Chrome

```bash
open -na "Google Chrome" --args --remote-debugging-port=19222 --user-data-dir="$HOME/chrome-debug"
```

### Edge

```bash
open -na "Microsoft Edge" --args --remote-debugging-port=19222 --user-data-dir="$HOME/edge-debug"
```

`open -na` always forces a new process instance, which is why (unlike double-clicking the Dock
icon) this reliably launches a second, isolated browser even if the app is already open.

### Verify the port is open

```bash
curl -s http://localhost:19222/json/version
```

Expect JSON output with browser/version fields.

## After a manually-launched debug browser is open

1. In the new browser window (not your normal one), navigate to your LeanIX workspace URL.
2. Log in normally.
3. Navigate around a little (e.g. open the Inventory) so at least one authenticated GraphQL/API
   request fires — `eahelper` needs to observe a real request to capture the Authorization header.
4. Leave this window open until the token is captured (with a manual launch, `eahelper` will not
   auto-close a browser it didn't start).
5. In a separate terminal, run `eahelper server --cdp-port 19222` (or whatever port you used).

## Skipping the browser entirely — Technical User API key

For automation, CI, or headless environments, you can skip browser/CDP entirely (managed or
manual) by using a LeanIX Technical User API key:

1. In LeanIX: **Administration → Technical Users → Create Technical User**, assign roles, copy the
   generated API key (shown once).
2. Pass it to the server:

```bash
eahelper server --api-token "your-api-key-here"
# or
export LEANIX_API_TOKEN="your-api-key-here"     # macOS/Linux
eahelper server
```

```powershell
$env:LEANIX_API_TOKEN = "your-api-key-here"      # Windows
eahelper server
```

The server exchanges the key for a Bearer token via OAuth2 client-credentials at startup, and
automatically re-exchanges it whenever the token expires — no browser needed at all, managed or
manual.

## Notes on profile/user-data-dir paths

- The managed browser's persistent profile lives at `~/.eahelper/browser-profile`. Deleting it
  forces a fresh login next time (useful if SSO gets into a bad state).
- For the manual fallback, any writable directory works; the examples above
  (`C:\Temp\edge-debug`, `~/chrome-debug`) are just conventions. Keep it separate from your default
  profile.
- The directory is created automatically if it doesn't exist.
- Re-using the same debug directory across sessions preserves cookies/login — you may not need to
  log in again on subsequent runs, as long as the browser was closed cleanly.
