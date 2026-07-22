"""Tiny zero-dependency .env loader used by the bundled scripts.

Looks for a `.env` file (repo root, then current dir, then ~) and loads simple
KEY=VALUE lines into os.environ — but never overwrites a variable that is already
set in the real environment. Quotes around values are stripped; `#` comments and
blank lines are ignored; lines may optionally start with `export `.
"""
import os
from pathlib import Path


def _candidate_paths():
    here = Path(__file__).resolve()
    # scripts/db/_envload.py (this repo) -> repo root is parents[2]
    repo_root = here.parents[2] if len(here.parents) >= 3 else here.parent
    seen = set()
    for p in (repo_root / ".env", Path.cwd() / ".env", Path.home() / ".env"):
        rp = p.resolve()
        if rp not in seen:
            seen.add(rp)
            yield rp


def load_dotenv(verbose: bool = False) -> int:
    loaded = 0
    for path in _candidate_paths():
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.lower().startswith("export "):
                line = line[7:].strip()
            if "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip()
            if (len(val) >= 2) and ((val[0] == val[-1] == '"') or (val[0] == val[-1] == "'")):
                val = val[1:-1]
            if not key or val == "":
                continue
            if key in os.environ:  # real environment wins
                continue
            os.environ[key] = val
            loaded += 1
        if verbose:
            print(f"[_envload] loaded {loaded} var(s) from {path}")
        break  # first .env found wins
    return loaded


if __name__ == "__main__":
    n = load_dotenv(verbose=True)
    print(f"loaded {n} variable(s)")
