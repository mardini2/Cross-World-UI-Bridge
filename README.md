# Cross-World UI Bridge (Windows · Python)

Control real GUI apps from a clean CLI. Bridge terminal ↔ GUI on Windows.

## Quick Start (Dev)
```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

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

# Spotify setup (per user, no secrets in repo)
python -m app.cli.cli spotify config set-client-id "YOUR_CLIENT_ID"
python -m app.cli.cli spotify login
python -m app.cli.cli spotify play "a moment apart odesza"

# word
python -m app.cli.cli word count "C:\path\to\doc.docx"

# windows UI
python -m app.cli.cli window list
python -m app.cli.cli window focus "Notepad"
```
