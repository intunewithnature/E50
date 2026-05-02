# Corpus Inspection: Project Gutenberg #100 (Complete Works of Shakespeare)

Pre-cleaning observations from a hand-read of `pg100.txt` (5,638,483 bytes,
196,074 lines, sha256 `041e8f1d…`). These decisions feed the cleaner script
in Step 5.

## Structural anchors (confirmed)

- **Header end:** line 25 — `*** START OF THE PROJECT GUTENBERG EBOOK …`
- **Footer start:** line 196048 — `*** END OF THE PROJECT GUTENBERG EBOOK …`
- **Last content line before footer:** `FINIS` at line 196044 (end-of-corpus
  marker, not per-play).
- **Master ToC:** lines ~37–83 (~43 entries: `THE SONNETS`, 38 dramatic
  works, 5 narrative poems). Indented 4 spaces, all-caps titles.
- **Per-play ToC:** appears immediately before each `Dramatis Personæ`. Has
  the shape `ACT I` / `Scene I. <location>.` / `Scene II. <location>.` …
  packed together with no body text between. Distinguishable from real
  ACT/SCENE markers in the body because the body never lists multiple
  scenes consecutively without speech between them.
- **Dramatis Personæ heading:** uses the æ ligature **only** (`Dramatis
  Personæ`). No occurrences of plain-ae `Dramatis Personae` in this file.
  Heading sometimes flush, sometimes indented one space.
- **Play setting line:** `SCENE. <location>.` (no roman numeral) appears
  between Dramatis Personæ and `ACT I`, e.g. `SCENE. Elsinore.` This is
  the play-level setting marker, not a scene break. Strip with the DP block.

## Strip rules (remove from corpus)

1. **Project Gutenberg header** — strip line 1 through the canonical
   `*** START OF` marker line (inclusive).
2. **Project Gutenberg footer** — strip from the canonical `*** END OF`
   marker line (inclusive) through end of file.
3. **Master table of contents** at the top of the file (~43 indented
   all-caps title lines after the file's `*** START OF` marker, before
   `THE SONNETS` body content begins).
4. **Per-play tables of contents** — `ACT [IVX]+` / `Scene N. <text>.`
   clusters that appear immediately before a `Dramatis Personæ` heading.
   Tolerant of leading whitespace.
5. **Dramatis Personæ blocks** — heading line through the line before
   the first `ACT I` body marker (which itself follows the `SCENE.
   <location>.` setting line — strip the setting line too).
6. **`FINIS`** sentinel line near end-of-corpus. Editorial marker, not
   text.
7. **Inline aside / address tags** — bracketed editorial commentary
   inside a line of speech. Forms observed:
   - `[Aside]` (no period — bare form is most common, e.g. Much Ado)
   - `[Aside to X.]` (with period when followed by a name)
   - `[To X.]`, `[To himself.]`
   - `[Within.]`, `[Aloud.]`, `[Sings.]`, `[Reads.]`
   - `[_Kneeling._]`, `[_Rising_.]`, `[_To the Groom_.]` (italicized
     editorial form)
   - `(_Sings_.)`, `(_Sings_)` (parenthetical italicized form attached
     to speaker lines, e.g. `AMIENS. (_Sings_.)`)
   These are interpretive editorial additions, not Shakespeare's text.
   Strip both bracketed and italicized-parenthetical variants.
8. **All underscores globally** — Project Gutenberg italics markup
   (`_word_`). 4,711 occurrences. Strip the underscores, keep the
   surrounding text. (Combine with rule 7: parenthetical/bracketed
   italicized stage notes get stripped whole; surviving inline italics
   like emphasis just lose the underscores.)

## Normalize rules (transform but keep)

1. **Speaker tags** — change `HAMLET.` (and multi-word `KING OF FRANCE.`,
   joint `VARRO. CLAUDIUS.`) to `HAMLET:` / `KING OF FRANCE:` /
   `VARRO. CLAUDIUS:`. Match: a line that is **entirely** all-caps words
   (with spaces and possibly internal periods for joint tags),
   terminated by a single `.`. Speech text starts on the next line, not
   inline. Keep the colon-replacement as the only change.
2. **Bare stage directions** — wrap in brackets. Lines whose first word
   (after optional leading whitespace) is one of: `Enter`, `Exit`,
   `Exeunt`, `Re-enter`, `Sound`, `Flourish`, `Alarum`, `Drum`,
   `Trumpet`. Trigger word list is the starting point; cleaner should be
   expandable via config. Many of these lines have a single leading
   space in the source (e.g. ` Enter Bertram, …`); trim before wrapping.

## Keep as-is

1. **Bracketed line-level stage directions:** `[Enter X.]`, `[Exit X.]`,
   `[Exeunt.]`, `[Exit Boy.]`, `[Exeunt Don Pedro, Claudio and
   Leonato.]`. Real structural signal — these are the canonical form.
2. **`ACT [IVX]+`** and **`SCENE [IVX]+. <location>.`** markers in the
   body of plays (the ones that have speech between them — not the ToC
   versions). Real structural breaks.
3. **Play titles** when they appear as section headers (all-caps title
   alone on a line at a play boundary).
4. **THE SONNETS** numbered headers (`                    1`, `2`, …) and
   the narrative poems' section structure.
5. **Smart/curly quotes** (`'`, `'`, `"`, `"`) — leave as-is.
   Period voice; don't flatten to ASCII.
6. **Original spelling and archaic forms** (`thee`, `thou`, `'tis`,
   `&c.`, `o'er`, `'twas`, contractions like `mak'st`, `feel'st`).
   Period voice is the demo.
7. **Em dashes** (`—`, U+2014). Source uses one form consistently.
   No normalization needed.

## Edge cases to confirm in cleaner

- **Multi-speaker lines** like `VARRO. CLAUDIUS.` (two characters
  speaking together): treat as a single speaker tag, period-to-colon
  rule applies once at the end.
- **Speaker tag with attached parenthetical** like `AMIENS. (_Sings_.)`:
  strip the `(_Sings_.)`, normalize the speaker tag, keep the line.
  Result: `AMIENS:`.
- **Speaker tag with attached bracketed direction** like `MOWBRAY.
  [_Rising_.]` or `HELICANUS. [_Kneeling._]`: same treatment — strip
  the bracketed editorial, normalize speaker tag.
- **Indentation variance:** stage directions, Dramatis Personæ
  headings, and some ACT lines appear with 0–2 leading spaces. Cleaner
  should be tolerant of leading whitespace on every match.
- **`SCENE.` vs `SCENE I.`:** the no-numeral form is a play-level
  setting marker (strip with DP block); the numeral form is a body
  scene break (keep).

## Output spec

- Single concatenated UTF-8 plain text file at
  `phase1_corpus/clean/corpus.txt`.
- Unicode normalization: NFC.
- Manifest at `phase1_corpus/manifest.csv` recording: source file,
  sha256 before, sha256 after, byte counts, line counts before/after,
  decisions applied (config flag set).
- Cleaner is **idempotent**: safe to re-run on the same `raw/` folder.
  Re-running on already-cleaned input should be a no-op or produce
  byte-identical output.
- Cleaner is **config-driven**: same script with config flags will run
  on Phase 2's Lovecraft + CAS corpus later. Config controls which
  strip/normalize rules apply per-corpus.

## Known cleaner caveats

- **Residual per-play ToC noise on plays with double-blank act
  separators.** Rule 6's cluster detector tolerates a single blank line
  between in-cluster lines. Plays whose per-play ToC separates each
  ACT/Scene-list block with **two** consecutive blank lines (All's Well
  That Ends Well demonstrated; likely affects others) get only their
  ACT I sub-cluster stripped — the ACT II/III/IV/V scene-list lines
  remain in `corpus.txt`. This is scene-list filler (e.g., `Scene I.
  Paris. A room in the King's palace.`), not Shakespeare body text, so
  it does not corrupt training. Intentionally not fixed in v1; revisit
  if the residual lines show up as a recognizable pattern in samples
  from the trained model.
