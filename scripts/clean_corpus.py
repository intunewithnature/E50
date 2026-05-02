"""E50 corpus cleaner.

Profile-driven pipeline that strips editorial / source-format noise from a
raw text corpus and writes a clean concatenated UTF-8 file plus a per-run
manifest row.

Usage
-----
    python scripts/clean_corpus.py
    python scripts/clean_corpus.py --profile shakespeare --verbose
    python scripts/clean_corpus.py --dry-run
    python scripts/clean_corpus.py --profile lovecraft        # Phase 2 stub

Source of truth for the Shakespeare profile rules is
``notes/corpus_inspection.md`` at repo root. If that document and this
script disagree, the inspection notes win.

Standard library only.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = REPO_ROOT / "phase1_corpus" / "raw" / "pg100.txt"
DEFAULT_OUTPUT = REPO_ROOT / "phase1_corpus" / "clean" / "corpus.txt"
DEFAULT_MANIFEST = REPO_ROOT / "phase1_corpus" / "manifest.csv"


# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------

STAGE_DIRECTION_TRIGGERS = (
    "Enter",
    "Re-enter",
    "Exit",
    "Exeunt",
    "Sound",
    "Flourish",
    "Alarum",
    "Drum",
    "Trumpets",
    "Music",
)

STAGE_DIRECTION_MULTIWORD_PREFIXES = (
    "A noise",
    "A cry",
    "A shout",
    "A trumpet",
)

# Multi-word movement-verb directions in brackets that we KEEP. Rule 10 must
# not strip these even though they look like single-word direction matches at
# a glance.
PRESERVE_BRACKET_PHRASE_FIRST_WORDS = ("Enter", "Exit", "Exeunt", "Re-enter")

# Inline editorial commentary tags to strip globally. Order in the list does
# not matter; all are tried per-line.
STRIP_INLINE_BRACKET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\[Aside\]"),
    re.compile(r"\[Aside to [^\]]+\]"),
    re.compile(r"\[To [^\]]+\]"),
    re.compile(r"\[Within\.?\]"),
    re.compile(r"\[To himself\.?\]"),
    re.compile(r"\[To herself\.?\]"),
    re.compile(r"\[To them\.?\]"),
)

# Rule 10 source patterns (post underscore strip).
RE_BRACKETED_SINGLE_WORD = re.compile(r"\[([A-Z][a-z]+)\.?\]")
RE_PARENTHESIZED_SINGLE_WORD = re.compile(r"\(([A-Z][a-z]+)\.?\)")

# Rule 12: speaker-tag line ending with bracketed/parenthesized direction.
RE_SPEAKER_WITH_ATTACHED = re.compile(
    r"^(\s*[A-Z][A-Z\s\.]*?\.)\s*[\[\(][^\]\)]+[\]\)]\s*$",
    re.MULTILINE,
)

# Rule 14: speaker tag normalization (line-final period → colon).
RE_SPEAKER_TAG = re.compile(r"^(\s{0,2}[A-Z][A-Z\s\.]*?)\.(\s*)$", re.MULTILINE)

# Structural anchors.
RE_GUTENBERG_START = re.compile(
    r"^\*{2,3}\s*START OF (?:THE |THIS )?PROJECT GUTENBERG.*$", re.MULTILINE
)
RE_GUTENBERG_END = re.compile(
    r"^\*{2,3}\s*END OF (?:THE |THIS )?PROJECT GUTENBERG.*$", re.MULTILINE
)
RE_DRAMATIS_PERSONAE = re.compile(r"^\s*Dramatis Personæ\s*$", re.MULTILINE)
RE_ACT_BODY = re.compile(r"^\s*ACT [IVXLC]+\s*\.?\s*$", re.MULTILINE)
RE_SCENE_BODY = re.compile(r"^\s*SCENE [IVXLC]+\.", re.MULTILINE)
RE_SCENE_NUMERAL_LINE = re.compile(r"^\s*Scene [IVXLC]+\.", re.MULTILINE)
RE_SCENE_SETTING_NO_NUMERAL = re.compile(r"^\s*SCENE\.\s.*$", re.MULTILINE)
RE_FINIS = re.compile(r"^\s*FINIS\.?\s*$", re.MULTILINE)


# ---------------------------------------------------------------------------
# Rule helpers
# ---------------------------------------------------------------------------

def _is_speaker_tag_line(line: str) -> bool:
    """True if the line is a standalone all-caps speaker tag ending in period."""
    stripped = line.strip()
    if not stripped or not stripped.endswith("."):
        return False
    body = stripped[:-1]
    if not body:
        return False
    # Allow letters, spaces, internal periods (joint-speaker forms).
    if not re.fullmatch(r"[A-Z][A-Z\s\.]*", body):
        return False
    return any(c.isalpha() for c in body)


def _first_word_lc(line: str) -> str:
    s = line.lstrip()
    if not s:
        return ""
    return re.split(r"\s+", s, maxsplit=1)[0].lower()


# ---------------------------------------------------------------------------
# Rules — each returns (new_text, count)
# ---------------------------------------------------------------------------

def rule_nfc(text: str) -> tuple[str, int]:
    """Rule 2: NFC unicode normalization."""
    return unicodedata.normalize("NFC", text), 0


def rule_strip_gutenberg_header(text: str) -> tuple[str, int]:
    """Rule 3: drop everything from start of file through *** START OF *** line."""
    m = RE_GUTENBERG_START.search(text)
    if not m:
        return text, 0
    return text[m.end():].lstrip("\r\n"), 1


def rule_strip_gutenberg_footer(text: str) -> tuple[str, int]:
    """Rule 4: drop everything from *** END OF *** line through end of file."""
    m = RE_GUTENBERG_END.search(text)
    if not m:
        return text, 0
    return text[: m.start()].rstrip() + "\n", 1


def rule_strip_master_toc(text: str) -> tuple[str, int]:
    """Rule 5: drop the master ToC at top of file (everything before first DP heading)."""
    m = RE_DRAMATIS_PERSONAE.search(text)
    if not m:
        return text, 0
    # Walk backwards from the DP match to find the start of the cluster of
    # body content immediately preceding it (e.g. THE SONNETS, narrative
    # poems). The master ToC is the indented all-caps title list at the
    # very top of the post-header text.
    head = text[: m.start()]
    # Identify candidate ToC region: a contiguous run of lines, mostly
    # 4-space-indented, all-caps title style, near the very top.
    lines = head.splitlines(keepends=True)
    toc_start = None
    toc_end = None
    for i, line in enumerate(lines):
        s = line.rstrip()
        is_toc_like = bool(
            re.match(r"^ {2,8}[A-Z][A-Z0-9 ,;:'’\.\-]+$", s)
            and len(s.strip()) > 2
        )
        if is_toc_like:
            if toc_start is None:
                toc_start = i
            toc_end = i
        else:
            if toc_start is not None and toc_end is not None and (i - toc_end) > 3:
                # The cluster ended a while ago; stop scanning.
                break
    if toc_start is None or toc_end is None:
        return text, 0
    new_lines = lines[:toc_start] + lines[toc_end + 1 :]
    return "".join(new_lines) + text[m.start():], 1


def rule_strip_per_play_tocs(text: str) -> tuple[str, int]:
    """Rule 6: drop per-play ToC clusters (consecutive 'Scene N.' / 'ACT N' lines)."""
    lines = text.splitlines(keepends=True)
    keep: list[str] = []
    i = 0
    count = 0
    n = len(lines)
    while i < n:
        # Scan forward for a candidate cluster.
        j = i
        scene_hits = 0
        act_hits = 0
        non_blank = 0
        while j < n:
            s = lines[j].rstrip()
            if not s:
                # Allow at most one blank within a cluster; bail otherwise.
                if j + 1 < n and (
                    RE_SCENE_NUMERAL_LINE.match(lines[j + 1])
                    or re.match(r"^\s*ACT [IVXLC]+\s*$", lines[j + 1])
                ):
                    j += 1
                    continue
                break
            if RE_SCENE_NUMERAL_LINE.match(lines[j]):
                scene_hits += 1
                non_blank += 1
            elif re.match(r"^\s*ACT [IVXLC]+\s*$", lines[j]):
                act_hits += 1
                non_blank += 1
            else:
                break
            j += 1
        # Confirm cluster: 3+ non-blank lines, majority Scene-numeral.
        if non_blank >= 3 and scene_hits >= 2 and scene_hits >= act_hits:
            count += 1
            i = j
            continue
        keep.append(lines[i])
        i += 1
    return "".join(keep), count


def rule_strip_dramatis_personae(text: str) -> tuple[str, int]:
    """Rule 7: strip Dramatis Personæ heading through pre-ACT setting lines."""
    lines = text.splitlines(keepends=True)
    keep: list[str] = []
    i = 0
    count = 0
    n = len(lines)
    while i < n:
        if RE_DRAMATIS_PERSONAE.match(lines[i]):
            # Find the first subsequent body-ACT or body-SCENE marker.
            j = i + 1
            while j < n:
                if (
                    re.match(r"^\s*ACT [IVXLC]+\s*$", lines[j])
                    or RE_SCENE_BODY.match(lines[j])
                ):
                    break
                j += 1
            i = j
            count += 1
            continue
        keep.append(lines[i])
        i += 1
    return "".join(keep), count


def rule_strip_finis(text: str) -> tuple[str, int]:
    """Rule 8: strip standalone FINIS sentinels."""
    new_text, n = RE_FINIS.subn("", text)
    return new_text, n


def rule_strip_underscores(text: str) -> tuple[str, int]:
    """Rule 9: strip all underscores (Gutenberg italics markup)."""
    n = text.count("_")
    return text.replace("_", ""), n


def rule_strip_single_word_directions(text: str) -> tuple[str, int]:
    """Rule 10: strip single-word bracketed/parenthesized stage directions.

    Honors PRESERVE_BRACKET_PHRASE_FIRST_WORDS — directions whose first word
    is a movement verb stay (those are line-level structural directions).
    A single preceding space is also consumed when present.
    """
    def _strip(pattern: re.Pattern[str], s: str) -> tuple[str, int]:
        local = 0

        def repl(m: re.Match[str]) -> str:
            nonlocal local
            word = m.group(1)
            if word in PRESERVE_BRACKET_PHRASE_FIRST_WORDS:
                return m.group(0)
            local += 1
            return ""

        wrapped = re.compile(r" ?" + pattern.pattern)
        return wrapped.sub(repl, s), local

    out, c1 = _strip(RE_BRACKETED_SINGLE_WORD, text)
    out, c2 = _strip(RE_PARENTHESIZED_SINGLE_WORD, out)
    return out, c1 + c2


def rule_strip_inline_asides(text: str) -> tuple[str, int]:
    """Rule 11: strip inline editorial brackets ([Aside], [To X.], etc.)."""
    total = 0
    out = text
    for pat in STRIP_INLINE_BRACKET_PATTERNS:
        wrapped = re.compile(r" ?" + pat.pattern)
        out, n = wrapped.subn("", out)
        total += n
    return out, total


def rule_strip_attached_directions(text: str) -> tuple[str, int]:
    """Rule 12: strip stage directions attached to speaker-tag lines.

    Example: ``HELICANUS. [Kneeling.]`` → ``HELICANUS.``
    The trailing period stays (Rule 14 normalizes it).
    """
    count = 0

    def repl(m: re.Match[str]) -> str:
        nonlocal count
        count += 1
        return m.group(1)

    return RE_SPEAKER_WITH_ATTACHED.sub(repl, text), count


def rule_wrap_bare_directions(text: str) -> tuple[str, int]:
    """Rule 13: wrap bare stage-direction lines in brackets.

    A line qualifies if all true:
      - 0-2 leading spaces
      - not a speaker tag
      - not already starting with '['
      - first word matches STAGE_DIRECTION_TRIGGERS, OR line begins with
        one of STAGE_DIRECTION_MULTIWORD_PREFIXES
    """
    triggers_lc = {t.lower() for t in STAGE_DIRECTION_TRIGGERS}
    multiword_lc = tuple(p.lower() for p in STAGE_DIRECTION_MULTIWORD_PREFIXES)
    out_lines: list[str] = []
    count = 0
    for line in text.splitlines(keepends=True):
        # Preserve trailing newline characters.
        if line.endswith("\r\n"):
            eol = "\r\n"
            body = line[:-2]
        elif line.endswith("\n"):
            eol = "\n"
            body = line[:-1]
        else:
            eol = ""
            body = line
        leading = len(body) - len(body.lstrip(" "))
        content = body.lstrip(" ")
        if (
            0 <= leading <= 2
            and content
            and not content.startswith("[")
            and not _is_speaker_tag_line(body)
        ):
            fw = _first_word_lc(content)
            content_lc = content.lower()
            if fw in triggers_lc or any(
                content_lc.startswith(p) for p in multiword_lc
            ):
                out_lines.append("[" + content + "]" + eol)
                count += 1
                continue
        out_lines.append(line)
    return "".join(out_lines), count


def rule_normalize_speaker_tags(text: str) -> tuple[str, int]:
    """Rule 14: speaker-tag line-final period → colon.

    Joint-speaker forms (``VARRO. CLAUDIUS.``) keep their internal period;
    only the line-final period is replaced.
    """
    count = 0

    def repl(m: re.Match[str]) -> str:
        nonlocal count
        body = m.group(1)
        # Avoid normalizing strays like a single short all-caps word that's
        # part of a sentence — but this regex is anchored to whole lines via
        # MULTILINE + `\s*$`, so any match is a full line. Still, require at
        # least one alphabetic char.
        if not any(c.isalpha() for c in body):
            return m.group(0)
        count += 1
        return f"{body}:{m.group(2)}"

    return RE_SPEAKER_TAG.sub(repl, text), count


def rule_collapse_newlines(text: str) -> tuple[str, int]:
    """Rule 15: collapse 3+ consecutive newlines to 2.

    CRLF-tolerant: matches \\r?\\n line endings. Replacement matches the
    file's predominant line-ending convention so this rule does not
    normalize line endings as a side effect.
    """
    crlf_count = text.count("\r\n")
    lf_count = text.count("\n") - crlf_count
    eol = "\r\n" if crlf_count > lf_count else "\n"
    out, n = re.subn(r"(?:\r?\n){3,}", eol * 2, text)
    return out, n


def rule_strip_trailing_ws(text: str) -> tuple[str, int]:
    """Rule 16: strip trailing whitespace from every line."""
    out_lines: list[str] = []
    count = 0
    for line in text.splitlines(keepends=True):
        if line.endswith("\r\n"):
            eol = "\r\n"
            body = line[:-2]
        elif line.endswith("\n"):
            eol = "\n"
            body = line[:-1]
        else:
            eol = ""
            body = line
        rstripped = body.rstrip()
        if rstripped != body:
            count += 1
        out_lines.append(rstripped + eol)
    return "".join(out_lines), count


# ---------------------------------------------------------------------------
# Profile config
# ---------------------------------------------------------------------------

# Each rule is (manifest_column_name, callable).
SHAKESPEARE_RULES: list[tuple[str, Callable[[str], tuple[str, int]]]] = [
    ("nfc_applied", rule_nfc),  # not in manifest spec but reserved
    ("gutenberg_header_stripped", rule_strip_gutenberg_header),
    ("gutenberg_footer_stripped", rule_strip_gutenberg_footer),
    ("master_toc_stripped", rule_strip_master_toc),
    ("per_play_tocs_stripped", rule_strip_per_play_tocs),
    ("dp_blocks_stripped", rule_strip_dramatis_personae),
    ("finis_sentinels_stripped", rule_strip_finis),
    ("underscores_stripped", rule_strip_underscores),
    ("single_word_directions_stripped", rule_strip_single_word_directions),
    ("inline_asides_stripped", rule_strip_inline_asides),
    ("attached_directions_stripped", rule_strip_attached_directions),
    ("bare_directions_wrapped", rule_wrap_bare_directions),
    ("speaker_tags_normalized", rule_normalize_speaker_tags),
    ("multi_newlines_collapsed", rule_collapse_newlines),
    ("trailing_ws_stripped", rule_strip_trailing_ws),  # reserved, not in manifest spec
]

CONFIG: dict[str, dict] = {
    "shakespeare": {
        "rules": SHAKESPEARE_RULES,
    },
    "lovecraft": {
        # TODO Phase 2: Lovecraft + CAS corpus profile
        # Rules likely needed:
        #   - strip_gutenberg_headers (reuse from shakespeare)
        #   - strip_lovecraft_footnote_markers
        #   - strip_lovecraft_footnote_bodies
        #   - strip_repeated_story_titles
        #   - strip_eldritch_dark_html_artifacts (CAS source)
        #   - normalize em dashes to U+2014
        # Implement when Phase 2 starts.
        "rules": [],
    },
}

# Manifest column order — matches the brief exactly.
MANIFEST_COLUMNS = [
    "timestamp_utc",
    "profile",
    "source_file",
    "sha256_in",
    "bytes_in",
    "sha256_out",
    "bytes_out",
    "lines_in",
    "lines_out",
    "gutenberg_header_stripped",
    "gutenberg_footer_stripped",
    "master_toc_stripped",
    "per_play_tocs_stripped",
    "dp_blocks_stripped",
    "finis_sentinels_stripped",
    "underscores_stripped",
    "single_word_directions_stripped",
    "inline_asides_stripped",
    "attached_directions_stripped",
    "bare_directions_wrapped",
    "speaker_tags_normalized",
    "multi_newlines_collapsed",
]


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def sha256_of_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run_pipeline(
    text: str,
    rules: list[tuple[str, Callable[[str], tuple[str, int]]]],
    verbose: bool,
) -> tuple[str, dict[str, int]]:
    counts: dict[str, int] = {}
    for name, fn in rules:
        text, c = fn(text)
        counts[name] = c
        if verbose:
            print(f"  {name}: {c}")
    return text, counts


def append_manifest(
    manifest_path: Path,
    row: dict[str, object],
) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not manifest_path.exists()
    with manifest_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=MANIFEST_COLUMNS)
        if new_file:
            writer.writeheader()
        writer.writerow({k: row.get(k, "") for k in MANIFEST_COLUMNS})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Clean a raw corpus into training-ready text."
    )
    parser.add_argument("--profile", default="shakespeare", choices=list(CONFIG))
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    profile_cfg = CONFIG[args.profile]
    rules = profile_cfg["rules"]
    if not rules:
        print(
            f"profile '{args.profile}' is stubbed — no rules defined yet. "
            "Implement when Phase 2 starts.",
            file=sys.stderr,
        )
        return 0

    if not args.input.exists():
        print(f"ERROR: input not found: {args.input}", file=sys.stderr)
        return 1

    raw_bytes = args.input.read_bytes()
    sha_in = sha256_of_bytes(raw_bytes)
    bytes_in = len(raw_bytes)
    text_in = raw_bytes.decode("utf-8")
    lines_in = text_in.count("\n") + (0 if text_in.endswith("\n") else 1)

    print(f"profile: {args.profile}")
    print(f"input:   {args.input} ({bytes_in:,} bytes, {lines_in:,} lines)")
    print(f"sha256:  {sha_in}")
    if args.verbose:
        print("rule counts:")

    text_out, counts = run_pipeline(text_in, rules, args.verbose)

    out_bytes = text_out.encode("utf-8")
    sha_out = sha256_of_bytes(out_bytes)
    bytes_out = len(out_bytes)
    lines_out = text_out.count("\n") + (0 if text_out.endswith("\n") else 1)

    print(f"output:  {args.output} ({bytes_out:,} bytes, {lines_out:,} lines)")
    print(f"sha256:  {sha_out}")

    if not args.verbose:
        # Final summary of nonzero rule counts.
        nz = {k: v for k, v in counts.items() if v}
        if nz:
            print("rule counts (nonzero):")
            for k, v in nz.items():
                print(f"  {k}: {v}")

    if args.dry_run:
        print("dry-run: no files written")
        print("OK")
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(out_bytes)

    row: dict[str, object] = {
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "profile": args.profile,
        "source_file": str(args.input.relative_to(REPO_ROOT))
        if args.input.is_absolute() and REPO_ROOT in args.input.parents
        else str(args.input),
        "sha256_in": sha_in,
        "bytes_in": bytes_in,
        "sha256_out": sha_out,
        "bytes_out": bytes_out,
        "lines_in": lines_in,
        "lines_out": lines_out,
    }
    for col in MANIFEST_COLUMNS[9:]:
        row[col] = counts.get(col, 0)

    append_manifest(args.manifest, row)
    print(f"manifest: appended row to {args.manifest}")
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
