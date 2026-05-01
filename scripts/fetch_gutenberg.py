"""Fetch Project Gutenberg ebook #100 (Complete Works of Shakespeare) for E50 Phase 1.

Idempotent: re-running with the file already present and a matching SHA256 in
SOURCES.md is a no-op. Standard library only.
"""

import hashlib
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = REPO_ROOT / "phase1_corpus" / "raw"
OUT_PATH = RAW_DIR / "pg100.txt"
SOURCES_PATH = RAW_DIR / "SOURCES.md"

PRIMARY_URL = "https://www.gutenberg.org/cache/epub/100/pg100.txt"
FALLBACK_URL = "https://www.gutenberg.org/files/100/100-0.txt"
USER_AGENT = "E50-CorpusBuilder/1.0 (https://github.com/intunewithnature/E50; jer@impious.io)"
TIMEOUT_S = 30

SOURCES_HEADER = (
    "# Phase 1 Raw Sources\n\n"
    "| File | Source URL | Fetched (UTC) | Bytes | SHA256 |\n"
    "|------|------------|---------------|-------|--------|\n"
)


def fail(msg: str, code: int = 1):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def existing_sha_in_sources(filename: str) -> str | None:
    if not SOURCES_PATH.exists():
        return None
    for line in SOURCES_PATH.read_text(encoding="utf-8").splitlines():
        if line.startswith("|") and f" {filename} " in line:
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 5:
                return cells[4]
    return None


def fetch(url: str) -> bytes:
    print(f"Fetching: {url}")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
        return resp.read()


def verify(data: bytes) -> None:
    if not data:
        fail("downloaded zero bytes")
    head = data[:500].decode("utf-8", errors="replace")
    if "Project Gutenberg" not in head:
        suspect = OUT_PATH.with_suffix(".txt.suspect")
        suspect.parent.mkdir(parents=True, exist_ok=True)
        suspect.write_bytes(data)
        fail(
            f"response does not look like a Gutenberg text "
            f"('Project Gutenberg' not in first 500 bytes); saved to {suspect}"
        )


def record_source(url: str, byte_len: int, sha: str) -> bool:
    """Append a row to SOURCES.md. Returns True if written, False if already present."""
    if existing_sha_in_sources(OUT_PATH.name) is not None:
        return False
    SOURCES_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not SOURCES_PATH.exists():
        SOURCES_PATH.write_text(SOURCES_HEADER, encoding="utf-8")
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    row = f"| {OUT_PATH.name} | {url} | {ts} | {byte_len:,} | {sha} |\n"
    with SOURCES_PATH.open("a", encoding="utf-8") as f:
        f.write(row)
    return True


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    if OUT_PATH.exists():
        local_sha = sha256_of(OUT_PATH)
        recorded = existing_sha_in_sources(OUT_PATH.name)
        if recorded is None:
            fail(
                f"{OUT_PATH} exists but no SOURCES.md row found; "
                f"refusing to overwrite. Local sha256={local_sha}"
            )
        if recorded != local_sha:
            fail(
                f"{OUT_PATH} sha256 mismatch — local={local_sha} "
                f"recorded={recorded}; refusing to overwrite"
            )
        print(f"already present: {OUT_PATH}")
        print(f"sha256 matches recorded value, no action: {local_sha}")
        print("OK")
        return

    data: bytes | None = None
    used_url: str | None = None
    try:
        data = fetch(PRIMARY_URL)
        used_url = PRIMARY_URL
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(f"primary URL returned 404, trying fallback")
            try:
                data = fetch(FALLBACK_URL)
                used_url = FALLBACK_URL
            except Exception as e2:
                fail(f"fallback fetch failed: {e2}")
        else:
            fail(f"primary fetch HTTP error: {e}")
    except Exception as e:
        fail(f"primary fetch failed: {e}")

    assert data is not None and used_url is not None

    print(f"bytes received: {len(data):,}")
    verify(data)

    OUT_PATH.write_bytes(data)
    sha = sha256_of(OUT_PATH)
    print(f"sha256: {sha}")
    print(f"wrote: {OUT_PATH}")

    wrote_row = record_source(used_url, len(data), sha)
    print(f"SOURCES.md: {'updated' if wrote_row else 'entry already present, no change'}")
    print("OK")


if __name__ == "__main__":
    main()
