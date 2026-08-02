import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HIGH_COLOR = "#BF5700"
SKIP_DIRS = {".venv", ".venv-build", "node_modules", "__pycache__", ".git", "build", "dist"}
STALE_ORANGE = re.compile(r"'orange'|\"orange\"|#FFA500", re.IGNORECASE)


def _source_files():
    this_file = Path(__file__).resolve()
    for path in REPO_ROOT.rglob("*"):
        if path == this_file or not path.is_file() or path.suffix not in {".html", ".py", ".js"}:
            continue
        if SKIP_DIRS & set(path.relative_to(REPO_ROOT).parts):
            continue
        yield path


def test_high_status_color_used_in_frontend():
    for name in ("static/widget.html", "static/index.html"):
        assert HIGH_COLOR in (REPO_ROOT / name).read_text()


def test_no_stale_low_contrast_orange():
    # Regression guard: 'orange'/#FFA500 has ~1.0-1.3:1 contrast against the LCD
    # screen and must not creep back in anywhere else (e.g. a future renderer
    # copying statusColor()'s old logic) now that #BF5700 replaced it.
    offenders = [str(path.relative_to(REPO_ROOT)) for path in _source_files() if STALE_ORANGE.search(path.read_text(errors="ignore"))]
    assert not offenders, f"stale low-contrast orange found in: {offenders}"
