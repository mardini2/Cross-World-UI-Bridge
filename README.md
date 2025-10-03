# UIBridge CLI (Windows)

Control real desktop apps from a simple command line. Run a small local agent and use an easy CLI to open pages, control Spotify, get a Word document word count, and focus windows on your PC.

---

## What’s included

- **UIBridgeLauncher.exe** — small helper window that starts the agent and opens a console for the CLI.
- **UIBridge.exe** — the local agent (FastAPI). Runs only on your machine.
- **ui.exe** — the command-line tool you type in the console.
- **Helper scripts** — `Open UIBridge CLI.cmd` and `Start UIBridge Agent.cmd` for quick starts.

No telemetry. Tokens are stored in **Windows Credential Manager**. Everything runs locally.

---

## For regular users

### 1) Download and unzip

Download the latest **UIBridge-Windows.zip** from the project’s Releases page and unzip it anywhere you like, for example your Desktop.

After unzipping, you should have a folder like:

```
UIBridge-Windows/
├─ UIBridgeLauncher.exe
├─ Open UIBridge CLI.cmd
├─ Start UIBridge Agent.cmd
├─ ui/
│  └─ ui.exe
└─ UIBridge/
   └─ UIBridge.exe
```

> If Windows Defender or SmartScreen warns about an unknown app, choose **More info** → **Run anyway**. This is expected for unsigned binaries.

### 2) Start the agent and open the CLI

- Double-click **UIBridgeLauncher.exe**.
- Click **Start Agent** if it is not already running.
- Click **Open CLI Console**. A console window opens in the `ui/` folder where you can run `ui` commands.

### 3) Try a few commands

```powershell
ui open youtube          # open YouTube
ui search lo-fi          # web search in your default browser
ui now                   # if Spotify is linked, show current track
```

### 4) Link Spotify (one-time)

You need a **Spotify Client ID** from the Spotify Developer Dashboard. It is public and not a secret. We use PKCE, so no client secret is required.

1. Go to https://developer.spotify.com → Dashboard → Create an app.
2. Copy the **Client ID**.
3. In the CLI run:

```powershell
ui setup
```

Paste the Client ID when asked. A browser tab opens to link your Spotify account. When it says “Spotify linked”, try:

```powershell
ui play "drake"
ui now
ui pause
```

### 5) Everyday quick reference

```powershell
ui open example.com      # URL or plain words (plain words become a search)
ui search "red pandas"   # open search results
ui browser launch        # start Edge with DevTools (for tab control)
ui browser tabs          # list tabs
ui play "lofi beats"     # Spotify play
ui now                   # who’s playing
ui pause                 # pause playback
ui word count "C:\Docs\file.docx"     # Word count via Microsoft Word
ui window list           # list open windows
ui window focus "Notepad"
```

> Tip: use the **Open UIBridge CLI.cmd** file in the zip to open a console with the right working directory if you are not using the Launcher.

### Troubleshooting

- **“Agent is not responding”**
  Click **Start Agent** in the launcher, then run your command again. If you still see a connection error, your firewall may be blocking localhost. Allow the app on **Private networks**.
- **“failed to load Python DLL” when starting UIBridge.exe**
  Install **Microsoft Visual C++ 2015–2022 Redistributable (x64)** from Microsoft.
- **Browser open fails**
  Click **Start Agent** in the launcher first. Then run `ui browser launch` and retry `ui open ...`.
- **Spotify login loops or shows an error**
  Run `ui setup` again, paste the Client ID, and retry. Spotify may require a Premium account for remote playback control on some endpoints.

---

## For developers

### Requirements

- Windows 10/11
- Python 3.11
- Microsoft Edge installed (for DevTools control)
- Microsoft Word installed (for Word count features)

### Quick Start (Dev)

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
pip install pyinstaller

# sanity check
pytest -q

# run agent
uvicorn app.main:app --host 127.0.0.1 --port 5025 --reload

# in another terminal
python -m app.cli.cli doctor
python -m app.cli.cli ping

# browser (Edge via CDP)
python -m app.cli.cli browser launch
python -m app.cli.cli browser open "https://example.com"
python -m app.cli.cli browser tabs

# Spotify (per-user, no secrets in repo)
python -m app.cli.cli spotify config --set-client-id "YOUR_CLIENT_ID"
python -m app.cli.cli spotify login
python -m app.cli.cli spotify play "a moment apart odesza"

# Word
python -m app.cli.cli word count "C:\path\to\doc.docx"

# Windows UI
python -m app.cli.cli window list
python -m app.cli.cli window focus "Notepad"
```

### CLI quality and local hooks

We ship config for Black, Ruff, isort, mypy, and pytest. Use **pre-commit** to match CI before you push:

```powershell
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

### Environment

Optional environment variables:

- `UIB_HOST` (default `127.0.0.1`)
- `UIB_PORT` (default `5025`)

### Project layout

```
app/
  adapters/           # Edge CDP, Spotify, COM, window utils
  auth/               # PKCE OAuth and token storage
  cli/                # Typer-based CLI entry points
  services/           # Thin wrappers used by API routes
  models/             # Pydantic schemas
  main.py             # FastAPI app factory
installer/
  version_info.txt    # Version metadata for PyInstaller
scripts/
  install_agent_startup.ps1
  uninstall_agent_startup.ps1
web-static/
  index.html          # GitHub Pages site
tests/
  ...                 # pytest suite
```

### Building Windows binaries (CI does this on tags)

The Release workflow builds three executables with PyInstaller:

- `UIBridgeLauncher.exe`
- `UIBridge.exe`
- `ui.exe`

Artifacts are zipped into **UIBridge-Windows.zip** with helper `.cmd` files.

### Security and privacy

- The local API uses a token header for private endpoints.
- Spotify tokens and the Spotify Client ID are stored in **Windows Credential Manager** via `keyring`.
- No analytics. No background network traffic beyond what you request.

### License

MIT
