"""Diagnostic: replay the cleaner pipeline through earlier rules, then dump strike line ranges + surrounding context for selected later-rule strikes (read-only, currently configured for Rule 6 per-play ToC clusters)."""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import clean_corpus as cc  # type: ignore


def main() -> None:
    raw = cc.DEFAULT_INPUT.read_bytes().decode("utf-8")

    # Run rules 2..5 to bring text to the same state Rule 6 sees.
    text, _ = cc.rule_nfc(raw)
    text, _ = cc.rule_strip_gutenberg_header(text)
    text, _ = cc.rule_strip_gutenberg_footer(text)
    text, _ = cc.rule_strip_master_toc(text)

    lines = text.splitlines(keepends=True)
    n = len(lines)

    # Re-implement Rule 6's detector but record (start, end_exclusive) of
    # each strike instead of stripping.
    strikes: list[tuple[int, int]] = []
    i = 0
    while i < n:
        j = i
        scene_hits = 0
        act_hits = 0
        non_blank = 0
        while j < n:
            s = lines[j].rstrip()
            if not s:
                if j + 1 < n and (
                    cc.RE_SCENE_NUMERAL_LINE.match(lines[j + 1])
                    or re.match(r"^\s*ACT [IVXLC]+\s*$", lines[j + 1])
                ):
                    j += 1
                    continue
                break
            if cc.RE_SCENE_NUMERAL_LINE.match(lines[j]):
                scene_hits += 1
                non_blank += 1
            elif re.match(r"^\s*ACT [IVXLC]+\s*$", lines[j]):
                act_hits += 1
                non_blank += 1
            else:
                break
            j += 1
        if non_blank >= 3 and scene_hits >= 2 and scene_hits >= act_hits:
            strikes.append((i, j))
            i = j
            continue
        i += 1

    print(f"detected {len(strikes)} per-play ToC strikes")
    print(f"(post-master-ToC line count: {n})")
    print()

    if not strikes:
        return

    targets = [
        ("1st", strikes[0]),
        ("27th", strikes[26]),
        ("54th", strikes[-1]),
    ]
    CONTEXT = 10
    for label, (start, end) in targets:
        print("=" * 78)
        print(f"STRIKE: {label}   lines {start + 1}..{end}  ({end - start} lines cut)")
        print("=" * 78)
        ctx_start = max(0, start - CONTEXT)
        ctx_end = min(n, end + CONTEXT)
        for idx in range(ctx_start, ctx_end):
            marker = "CUT >>>" if start <= idx < end else "       "
            line = lines[idx].rstrip("\n").rstrip("\r")
            print(f"{idx + 1:>7d} {marker} {line}")
        print()


if __name__ == "__main__":
    main()
