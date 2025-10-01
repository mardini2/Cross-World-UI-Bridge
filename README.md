# Cross-World UI Bridge (Windows · Python)

Control real GUI apps from a clean CLI. Bridge terminal ↔ GUI on Windows.

## Quick Start (Dev)
```powershell
python -m venv .venv
. .venv/Scripts/activate
pip install --upgrade pip
pip install -r requirements.txt

# run agent
uvicorn app.main:app --host 127.0.0.1 --port 5025 --reload

# in another terminal
python -m app.cli.cli doctor
python -m app.cli.cli ping

# browser (Edge via CDP)
python -m app.cli.cli browser launch
python -m app.cli.cli browser open "https://example.com"
python -m app.cli.cli browser tabs

# spotify
$env:SPOTIFY_CLIENT_ID="YOUR_CLIENT_ID"
python -m app.cli.cli spotify login   # complete in browser
python -m app.cli.cli spotify play "lofi"
python -m app.cli.cli spotify now

# word
python -m app.cli.cli word count "C:\path\to\doc.docx"

# windows UI
python -m app.cli.cli window list
python -m app.cli.cli window focus "Notepad"
```
