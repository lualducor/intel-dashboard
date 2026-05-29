import zipfile
from datetime import datetime, timezone
from pathlib import Path
from app.config import get_settings

APP_DIR = Path(__file__).resolve().parents[1] / "app"
PROJECT_DIR = Path(__file__).resolve().parents[1]

def _redact_env(env_path: Path) -> str:
    # read .env if it exists; for each non-comment KEY=VALUE line, keep KEY= and replace VALUE with "***REDACTED***". Return the redacted text (or "" if no .env).
    if not env_path.exists():
        return ""
    lines = []
    with env_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                lines.append(line)
                continue
            if "=" in line:
                key, _ = line.split("=", 1)
                lines.append(f"{key}=***REDACTED***")
            else:
                lines.append(line)
    return "\n".join(lines)

def export_config(*, out_dir=None) -> Path:
    s = get_settings()
    out_dir = Path(out_dir or s.export_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    dest = out_dir / f"config_{stamp}.zip"
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(APP_DIR / "sources.yaml", "sources.yaml")
        z.write(APP_DIR / "interests.yaml", "interests.yaml")
        env_path = PROJECT_DIR / ".env"
        redacted = _redact_env(env_path)
        if redacted:
            z.writestr("env.redacted", redacted)
    return dest

if __name__ == "__main__":
    print("config exported:", export_config())
