# Phase 1 Tokenizer Comparison

Trained: 2026-05-02T01:39:21Z
Corpus: `phase1_corpus/clean/corpus.txt` (sha256 `41c6561caf92be23cd8156ec3521df88036a9610316d87f379c05b75158ed96c`, 5,523,258 bytes, 191,616 lines)
Library: `tokenizers` 0.23.1

## Summary table

| Vocab (target) | Actual vocab | Merges | Training time | Tokens-per-byte | Total tokens (corpus) | Avg merge length |
|---:|---:|---:|---:|---:|---:|---:|
| 256 | 259 | 0 | 1.31s | 1.0000 | 5,523,258 | 0.00 |
| 1024 | 1024 | 765 | 1.95s | 0.4347 | 2,400,871 | 3.39 |
| 4096 | 4096 | 3837 | 2.05s | 0.3400 | 1,878,092 | 4.66 |
| 16384 | 16384 | 16125 | 2.98s | 0.2956 | 1,632,540 | 5.92 |

## Round-trip integrity

Each passage encoded then decoded; `decoded == original` is the test.

| Vocab | first_500_chars | random_middle_500 | famous_line | stage_direction | speaker_with_dialogue |
|---:|:---:|:---:|:---:|:---:|:---:|
| 256 | ✓ (506 toks) | ✓ (510 toks) | ✓ (42 toks) | ✓ (15 toks) | ✓ (27 toks) |
| 1024 | ✓ (219 toks) | ✓ (243 toks) | ✓ (15 toks) | ✓ (7 toks) | ✓ (13 toks) |
| 4096 | ✓ (166 toks) | ✓ (168 toks) | ✓ (13 toks) | ✓ (4 toks) | ✓ (10 toks) |
| 16384 | ✓ (136 toks) | ✓ (157 toks) | ✓ (13 toks) | ✓ (4 toks) | ✓ (10 toks) |

## Probe word coverage

Per probe word: is the whole word a single token? If not, how does it split?

| Word | vocab=256 | vocab=1024 | vocab=4096 | vocab=16384 |
|:---|:---|:---|:---|:---|
| `the` | `t · h · e` | **whole** | **whole** | **whole** |
| `and` | `a · n · d` | **whole** | **whole** | **whole** |
| `thou` | `t · h · o · u` | `th · ou` | `th · ou` | **whole** |
| `hath` | `h · a · t · h` | `hat · h` | `hat · h` | **whole** |
| `HAMLET` | `H · A · M · L · E · T` | `H · AM · LE · T` | **whole** | **whole** |
| `MACBETH` | `M · A · C · B · E · T · H` | `M · AC · B · E · TH` | **whole** | **whole** |
| `[Enter` | `[ · E · n · t · e · r` | `[ · Enter` | `[ · Enter` | `[ · Enter` |
| `[Exit` | `[ · E · x · i · t` | `[ · Exit` | `[ · Exit` | `[ · Exit` |
| `lord` | `l · o · r · d` | `l · ord` | `l · ord` | **whole** |
| `king` | `k · i · n · g` | `k · ing` | **whole** | **whole** |
| `sword` | `s · w · o · r · d` | `sw · ord` | `sw · ord` | `sw · ord` |
| `love` | `l · o · v · e` | `l · ove` | `l · ove` | **whole** |
| `death` | `d · e · a · t · h` | `de · ath` | `de · ath` | **whole** |
| `Yorick` | `Y · o · r · i · c · k` | `Y · or · ick` | `Y · or · ick` | `Y · or · ick` |

## First 20 merges per vocab size

### vocab=256

```
(no merges — vocab budget at or below alphabet size)
```

### vocab=1024

```
č Ċ
Ġ t
h e
Ġ a
o u
Ġ s
i n
Ġ m
Ġ w
r e
h a
n d
Ġt he
Ġ b
i s
e r
o r
â Ģ
l l
Ġ f
```

### vocab=4096

```
č Ċ
Ġ t
h e
Ġ a
o u
Ġ s
i n
Ġ m
Ġ w
r e
h a
n d
Ġt he
Ġ b
i s
e r
o r
â Ģ
l l
Ġ f
```

### vocab=16384

```
č Ċ
Ġ t
h e
Ġ a
o u
Ġ s
i n
Ġ m
Ġ w
r e
h a
n d
Ġt he
Ġ b
i s
e r
o r
â Ģ
l l
Ġ f
```

## Last 20 merges per vocab size

### vocab=256

```
(no merges — vocab budget at or below alphabet size)
```

### vocab=1024

```
it tle
ist ress
B ER
ĠC a
K E
Ġm aster
at ch
The y
S he
n e
S t
Ġf ell
hi p
m p
Ġs et
ĠI f
Ġmy self
m en
Ġt ong
Ġp ri
```

### vocab=4096

```
Ġapp are
ĠPr oteus
Ġfollow s
Ġtre asure
Ġaff airs
Ġwhe ther
ĠPer cy
Ġappro ach
ĠSil via
Ġarg ument
Ca esar
Ġmonst rous
COM INIUS
B l
V OST
W O
a ult
h or
h um
o ot
```

### vocab=16384

```
char ge
tong ue
Ġsevent een
Ġprim rose
Ġusure rs
Ġdesol ate
Ġpert urb
Ġobsc ured
miss ive
add ers
Ġdol our
Ġleather n
Ġwrang le
Ġscold ing
Ġpurg ation
Any thing
Ġcram med
Ġobst inate
Ġcele brate
Ġdetermin ation
```

## Observations

Tokens-per-byte falls monotonically from 1.0000 at vocab=256 to 0.2956 at vocab=16384. Each step up the vocab ladder adds merges that fold previously-multi-token patterns into single tokens, so the corpus encodes into fewer tokens overall. The largest absolute drop is between vocab=256 and vocab=1024, where common letter pairs and short words become single tokens; gains taper at the high end as the new merges target rarer phrase-level patterns.

Average vocabulary token length grows from 0.00 chars at vocab=256 to 5.92 chars at vocab=16384. At low vocab sizes the merges that exist are mostly two- or three-character fragments; by vocab=4096 and especially vocab=16384, the late merges cover whole common words and even short Shakespearean phrases.

Probe-word coverage (whole-word token, no splits) climbs across the four sizes: 0/14 at vocab=256, 2/14 at vocab=1024, 5/14 at vocab=4096, 10/14 at vocab=16384. Frequent function words like `the` and `and` become whole tokens early; play-name speaker tags like `HAMLET` and `MACBETH` only consolidate at the higher vocab sizes; rarer words like `Yorick` may remain split even at vocab=16384, and the `[Enter` / `[Exit` brackets — which the cleaner introduced — track when stage-direction patterns have folded into single tokens.
