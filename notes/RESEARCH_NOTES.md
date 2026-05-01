---
created: 2026-05-01
type: research
status: active
description: "Pre-execution research for the first LLM training run. Phase 1 calibration + Phase 2 Lovecraft/CAS corpus. Read before code."
---

# RESEARCH_NOTES

Pre-execution findings. Surfaces the things the brief asked us to verify, plus the things that changed between the brief being written and now.

---

## 0. Headline findings (read these first)

1. **The brief assumed CPU/MPS. This laptop has neither MPS nor a usable GPU.** AMD Ryzen 5 4600U + AMD Radeon integrated. No CUDA. No MPS (Apple-only). ROCm doesn't support Windows for this generation. **Pure CPU training only.** PyTorch will fall back to CPU.
2. **CPU-only training on consumer hardware is measured in weeks, not hours.** Discussion thread on nanochat #231 quotes ~41 days on a single consumer GPU vs. **~405 days CPU-only** for the full speedrun. The full speedrun is not the target. **Miniseries-scale or smaller is the only viable Phase 2 path.**
3. **The brief's primary corpus repo is dead.** `urbanadventurer/HP-Lovecraft-corpus` returns 404. Replacement identified: `vilmibm/lovecraftcorpus` (per-story files, what the brief described).
4. **Windows is a wrinkle.** nanochat-workshop README doesn't mention Windows. Recommendation: run inside WSL2 Ubuntu, not native Windows Python. Cleaner toolchain, fewer surprises.
5. **The "workshop fork advantage" has narrowed.** Karpathy mainline `nanochat` added its own `runs/runcpu.sh` after the Oct 2025 release, plus a Jan 7 2026 `miniseries.sh`. The i-dot-ai workshop fork is still fine but is no longer the only CPU-aware option.

---

## 1. Hardware probe (this laptop)

| Field | Value |
|-------|-------|
| OS | Windows 11 Pro 10.0.26200 |
| CPU | AMD Ryzen 5 4600U (Zen 2, 6C/12T, ~2.1 GHz base) |
| RAM | 13.9 GB |
| GPU | AMD Radeon (integrated, 2GB shared) — **not training-usable** |
| MPS | N/A (Apple-only) |
| CUDA | N/A (AMD) |
| ROCm | Unsupported on Windows for this APU |
| Disk free (C:) | 59.1 GB |
| Python | 3.12.10 (system) |
| Working dir | `C:\Users\Name\Documents\llm\` |

**Implication:** Every config needs to assume ~12 logical CPU cores, ~12 GB usable RAM, 50ish GB disk, no accelerator. Float32 training, small batch, gradient accumulation if needed. AVX2 yes, AVX-512 no.

**Recommendation:** Do Phase 1 in **WSL2 Ubuntu**, not native Windows. Pip wheels are cleaner, shell scripts run unmodified, BPE tokenizer training won't hit Windows pathing issues.

---

## 2. Stack: nanochat ecosystem state (May 2026)

### i-dot-ai/nanochat-workshop (the brief's pick)
- **Status:** Active. 224 commits on master. 0 open issues.
- **CPU script:** `dev/runcpu.sh` exists. Confirmed.
- **Last meaningful activity:** `miniseries.sh` added Jan 7 2026 (mirroring Karpathy's mainline addition).
- **Windows support:** Not addressed in README. Quote: *"nanochat can be run on CPU or on MPS (if you're on Macbook)... most of the code is fairly vanilla PyTorch so it should run on anything that supports that."* Implicit: WSL2 should work.
- **Honest assessment from their README:** *"You're not going to get too far without GPUs, but at least you'll be able to run the code paths."* They do not promise a useful model from CPU runs. They promise a working pipeline.

### karpathy/nanochat (upstream)
- **380 total commits** on master (more than the workshop fork).
- Added `runs/runcpu.sh` after Oct 2025 release.
- Added `miniseries.sh` Jan 7 2026 — this is the smaller-scale variant.
- Discussion #231 ("low-resource infrastructure") is the canonical thread for laptop runs.

### Karpathy newer work
- **`karpathy/autoresearch`** (~March 2026): AI agents running research on single-GPU nanochat training. Single-GPU only, not laptop-relevant. Skip.
- No newer "educational training repo" successor identified.

### Recommendation
**Use mainline `karpathy/nanochat` with `runs/runcpu.sh` + `miniseries.sh`** rather than the i-dot-ai fork. Reasons:
- Mainline is more actively maintained (380 vs 224 commits).
- Mainline now has its own CPU path, narrowing the fork's reason to exist.
- Fewer hops between "what Karpathy ships" and "what we run" makes debugging cleaner.

If mainline runcpu.sh proves broken on this machine, fall back to the i-dot-ai workshop fork. Not the other way around.

**This is a deviation from the brief.** Flagging explicitly. Operator should sign off before Phase 1 install.

---

## 3. Phase 2 corpus sources

### Lovecraft

| Source | URL | State | Notes |
|--------|-----|-------|-------|
| ~~urbanadventurer/HP-Lovecraft-corpus~~ | github.com/urbanadventurer/HP-Lovecraft-corpus | **404 / gone** | Brief's pick. Dead. |
| **vilmibm/lovecraftcorpus** | github.com/vilmibm/lovecraftcorpus | Live | Per-story files. Replacement primary source. |
| TristanBehrens/lovecraftcorpus | huggingface.co/datasets/TristanBehrens/lovecraftcorpus | Live | HF dataset, includes essays + letters. Backup. |
| Wikisource | en.wikisource.org/wiki/Author:H._P._Lovecraft | Live | 200+ works. Scrape fallback. |
| jrdnbradford/lovecraftr | R package | Live | Has raw text files. Backup. |

**Recommendation:** Pull `vilmibm/lovecraftcorpus` as primary. Cross-check coverage against Wikisource list. If gaps, fill from Wikisource.

### Clark Ashton Smith

- **eldritchdark.com is alive** (search results confirm). Direct fetch from this Claude session refused — likely UA block on their server. Real scraper with a sensible User-Agent should work.
- **URL pattern:** `eldritchdark.com/writings/short-stories/{numeric_id}/{slug}` — clean and predictable.
- **Index page:** `eldritchdark.com/writings/short-stories/` lists all stories with IDs.
- **Politeness plan:** 1 request / 2 sec, descriptive User-Agent ("LovecraftCASCorpusBuilder/1.0; contact: jer@..."). No threading. Cache locally; never re-scrape.
- **Backup:** Wikisource has CAS too if Eldritch Dark blocks scraping.

### Copyright (audit-trail only — operator stated he doesn't care for a laptop demo)

**Lovecraft (US):**
- Died 1937. All works first published before 1931 are PD via age.
- Most post-1931 works PD via non-renewal under pre-1978 law.
- Practically: **treat the entire HPL fiction + essays + letters corpus as PD.** No specific works flagged.

**Clark Ashton Smith (US):**
- Bulk PD: pre-1964 published stories with no copyright renewal. That's most of the fiction.
- Three known renewals:
  - *Nero and Other Poems* (1937, renewed) — but it's poetry, brief says skip poetry anyway.
  - *Out of Space and Time* (1942, renewed) — collection of stories. **Some of these stories were first published earlier in pulps (PD); some "previously unpublished" stories within it remain copyrighted until 2034.**
  - All works unpublished at his death — copyrighted until 2034.
- **Practical rule:** If a CAS story has a documented pulp magazine first-publication date pre-1964, it's PD. If it first appeared in *Out of Space and Time* (1942) or in posthumous collections, it may not be. Eldritch Dark sources are largely the pulp originals.
- For a laptop-only demo, immaterial. Documented for the audit trail.

---

## 4. Sanitization decisions to lock in (operator's call before he writes the cleaning script)

These are decision points the brief flagged. Pre-deciding them now avoids re-running the cleaner three times.

| Decision | Recommendation | Why |
|---|---|---|
| Em dash form | Normalize all to `—` (U+2014) | HPL used both `--` and `—`. Single form lets BPE merge cleanly. |
| Chapter break token | `\n\n\n` (no special token) | Special tokens cost vocab slots; this corpus is too small to spend them. |
| Footnotes | Strip both markers and bodies | They poison the prose register. Editorial intrusion. |
| Letters | **Include** for HPL | Voice-rich, distinctive. Reinforces the register. |
| HPL essays | **Include** | Same reason. |
| CAS poetry | Skip per brief | Confirmed: scansion contaminates prose generation. |
| Howard / Long / Blackwood / Derleth | Skip per brief | Voice purity is the demo. |
| HPL collaborations (with Bishop, Heald, etc.) | **Include but tag in manifest** | They're recognizably HPL-driven. Operator can drop later if voice muddies. |
| Encoding | UTF-8, normalize NFC | Some sources are latin-1; normalize on ingest. |
| Project Gutenberg headers | Strip via canonical `*** START OF` / `*** END OF` markers | Standard. |

---

## 5. Tokenizer plan

- **BPE, vocab 4096.** Brief said 4096 or 8192. With ~3M tokens of training corpus, 4096 is the safer choice — denser merges, fewer single-occurrence one-token-per-rare-word cells.
- **Special tokens:** `<|bos|>`, `<|eos|>`, `<|pad|>`. Skip `<|chapter|>`. Add `<|unk|>` only if BPE training shows OOV in eval.
- **Train:** sentencepiece or HF `tokenizers`. nanochat ships its own BPE trainer; use it for stack consistency.
- **Save:** vocab.json + merges.txt + a config snapshot recording vocab_size, special tokens, and the corpus sha256 (so the tokenizer is reproducible from corpus state).

---

## 6. Model & training plan (Phase 2 sketch — refine after Phase 1)

- **Params:** 15-20M as specified. Lean depth over width: e.g., n_layer=12, n_head=6, n_embd=384, ctx=512. ~21M params at vocab=4096.
- **Batch:** Tiny. Likely device_batch_size=4-8 with gradient accumulation to effective batch 32-64.
- **Precision:** float32 on CPU. bfloat16 won't help on Zen 2 (no native bf16 instructions; emulated cost > savings).
- **Optimizer:** AdamW, standard nanochat config.
- **Wallclock:** **Plan for multi-night.** Realistic estimate: 1-2 nights of training for first usable samples, possibly 4-6 nights for "best" checkpoint. We will know better after Phase 1 timing data.
- **Heat/throttling:** Laptop cooling is the real bottleneck. Plan to run plugged in, on a cooling pad if available, with the lid open.

---

## 7. Open questions for operator before Phase 1 starts

1. **Native Windows Python or WSL2 Ubuntu?** I recommend WSL2. Operator's call.
2. **Mainline `karpathy/nanochat` or i-dot-ai workshop fork?** I recommend mainline. Brief says workshop fork. **This is the deviation that needs explicit sign-off.**
3. **Disk budget.** 59 GB free. Corpus + tokenizer + checkpoints + datasets cache. Should be fine; flagging in case operator has other plans for this disk.
4. **Cooling pad / thermal plan?** Not blocking, but multi-night CPU pegged at 100% on a thin laptop is rough.

---

## 8. What's done in this research pass

- Hardware probed.
- Stack alternatives evaluated.
- Both corpus sources verified (one dead, one inaccessible-but-alive — both have replacements).
- Public domain status documented for audit trail.
- Sanitization decisions pre-staged.
- Phase 2 model plan sketched (subject to Phase 1 timing data).

## 9. What's NOT done (waiting for greenlight)

- No code cloned, no venv created, no installs run.
- No corpus downloaded.
- No scripts written.
- No commits.

Operator review next. After that, Phase 1 install begins.

---

## Sources

- [i-dot-ai/nanochat-workshop](https://github.com/i-dot-ai/nanochat-workshop)
- [karpathy/nanochat](https://github.com/karpathy/nanochat)
- [nanochat low-resource discussion #231](https://github.com/karpathy/nanochat/discussions/231)
- [karpathy/autoresearch](https://github.com/karpathy/autoresearch)
- [vilmibm/lovecraftcorpus](https://github.com/vilmibm/lovecraftcorpus)
- [TristanBehrens/lovecraftcorpus (HF)](https://huggingface.co/datasets/TristanBehrens/lovecraftcorpus)
- [Wikisource: H.P. Lovecraft](https://en.wikisource.org/wiki/Author:H._P._Lovecraft)
- [The Eldritch Dark](http://www.eldritchdark.com/)
- [HPL copyright status (Lovecraft Wiki)](https://lovecraft.fandom.com/wiki/Copyright_status_of_works_by_H._P._Lovecraft)
- [Stanford Copyright Renewals — CAS](https://exhibits.stanford.edu/copyrightrenewals/catalog?utf8=%E2%9C%93&exhibit_id=copyrightrenewals&search_field=search&q=Clark+Ashton+Smith)
- [LibriVox — Collected Public Domain Works of HPL](https://librivox.org/collected-public-domain-works-of-h-p-lovecraft/)
