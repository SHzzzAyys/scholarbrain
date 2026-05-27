# v0.2.2 Vocab Retrospective — what 12 real papers taught us

> Status: shipped as commit f73b2e4 on 2026-05-27
> Source: Dataview query simulation on `D:/ToxoVault/Research/Papers/*.md` (12 cards)
> Parent: HARDEN_PLAN.md v0.2.1 deferred items

---

## TL;DR

Running `/research-paper` on the 10-paper protozoa_top10 batch + 2 prior
cards (Toxo m5C, Attention) gave us 12 controlled-vocab samples. 3 problems
surfaced that were invisible during Day 1-3 design:

| # | Problem | Cards affected | v0.2.2 fix |
|---|---|---|---|
| 1 | LLM auto-coins tags not in vocab (IP-MS, FACS, U-ExM, bar-seq, WGS, population structure inference) | 6 of 12 | METHOD_TAGS_VOCAB: 50 → 59 |
| 2 | LLM emits Chinese tags (`免疫荧光`, `in vivo感染`) despite English vocab | 1 of 12 (Ulu) | TASK_PROMPT: explicit English-only rule + counter-example |
| 3 | Case-sensitivity drift (none seen yet, but LLM is non-deterministic) | 0 of 12 | TASK_PROMPT: explicit case rule (`CRISPR-Cas9` not `crispr-cas9`) |

---

## How the findings surfaced

The `Dataview query simulation` (Python YAML parser running the same logic as
Obsidian Dataview plugin) exposed `method_tags` distribution across all 12
cards. Two queries answered:

- Q1: `model_organism = "Toxoplasma gondii"` → 5 cards
- Q2: `contains(method_tags, "CRISPR-screen")` → 2 cards

But the BONUS Counter dump of all `method_tags` revealed the gaps:

```
6× CRISPR-Cas9    [in vocab ✅]
6× knockout       [in vocab ✅]
5× mass spec      [in vocab ✅]
4× flow cytometry [in vocab ✅]
4× co-IP          [in vocab ✅]
4× RNA-seq        [in vocab ✅]
3× other          [gap signal ⚠️]
...
1× IP-MS          [auto-coined ❌ → added]
1× FACS           [auto-coined ❌ → added]
1× U-ExM          [auto-coined ❌ → added]
1× bar-seq        [auto-coined ❌ → added]
1× whole-genome sequencing            [auto-coined ❌ → added]
1× population structure inference     [auto-coined ❌ → added]
1× 免疫荧光        [Chinese drift ❌ → constraint added]
1× in vivo感染     [Chinese drift ❌ → constraint added]
1× in vitro感染    [Chinese drift ❌ → constraint added]
```

---

## What v0.2.2 shipped

### Schema change: METHOD_TAGS_VOCAB 50 → 59

Added (organized by category):
- **Genome perturbation**: `bar-seq` (barcoded screens)
- **Sequencing**: `whole-genome sequencing` (was implicit, now explicit)
- **Protein-protein interaction**: `IP-MS` (immunoprecipitation + mass spec)
- **Imaging**: `U-ExM` (ultrastructure expansion microscopy)
- **Profiling**: `FACS` (alongside `flow cytometry`; LLM was already
  emitting FACS as a distinct intent)
- **Computational**: `population structure inference` (essential for
  protozoan epidemiology papers like Billows 2026)

### TASK_PROMPT change: 4 explicit rules

Added a "强制约束" subsection under method_tags:

1. **Strict English** — even when surrounding JSON is Chinese. Counter-example
   provided so LLM sees the exact failure mode: `["免疫荧光"]` → `["immunofluorescence"]`.
2. **Strict case-sensitivity** — `CRISPR-Cas9` not `CRISPR/Cas9` or `crispr-cas9`.
3. **Don't auto-coin** — if it's not in the vocab, use `"other"`, then add
   the missing concept to `_missing` (already part of schema).
4. **FACS vs flow cytometry disambiguation** — explicit guidance so the LLM
   doesn't switch arbitrarily.

---

## Verification

Re-ran `/research-paper` on `02_Bradyzoite_subtypes_rule_the_crossroads_of_Toxoplasma_development.pdf`
(originally produced `["RNA-seq", "scRNA-seq", "FACS", "免疫荧光"]`):

```
before:  ["RNA-seq", "scRNA-seq", "FACS", "免疫荧光"]
after:   ["RNA-seq", "scRNA-seq", "immunofluorescence", "FACS",
          "mouse infection", "flow cytometry"]
```

- ✅ Chinese tag `免疫荧光` → `immunofluorescence`
- ✅ Both `FACS` and `flow cytometry` correctly distinguished (paper used both)
- ✅ Bonus: now correctly picks up `mouse infection` (was missing before)
- ✅ All 6 tags now in vocab

---

## What stays unfixed (deferred to v0.3+)

| # | Issue | Why deferred |
|---|---|---|
| A | All 12 cards came out `result_direction: positive` | Already addressed in v0.2.1 TASK_PROMPT calibration; re-test on next batch |
| B | `novelty_type` / `position_in_field` use English short keys but Obsidian renders Chinese annotations in TASK_PROMPT | Cosmetic; English short keys are correct for cross-paper filtering |
| C | `CUT&RUN` outputs with YAML quotes (`"CUT&RUN"`) | YAML escapes `&` automatically; downstream dataview `contains()` still works. Not a bug |
| D | Re-extraction of the 10 protozoa batch under v0.2.2 not done yet | Cost-aware: existing cards still work; user can re-run on demand |

---

## Lessons for future controlled-vocab additions

1. **Real-world dump beats spec brainstorming**: We brainstormed 31 tags in
   v0.2, expanded to 50 in v0.2.1 from anticipated gaps, then 59 in v0.2.2 from
   actual gaps — and the v0.2.2 additions were qualitatively different from
   the v0.2.1 ones. Run real papers before each vocab freeze.
2. **LLM language drift is sneaky**: The TASK_PROMPT instructed Chinese output
   for most fields, but didn't explicitly carve out method_tags. The LLM
   "obeyed" the global rule even for fields where English is correct.
   Lesson: per-field language rules > global ones.
3. **Counter-examples in prompt beat positive rules**: Adding the literal
   `["免疫荧光"]` → `["immunofluorescence"]` example made the rule sticky.
   Pure "use English" had been there since v0.2 in the cross-vocab note but
   was ignored under Chinese context pressure.
4. **Stratify the dataview "BONUS" query as a regression check**: After every
   batch run, dump the full `method_tags` distribution. New 1-count tags are
   either real new methods (extend vocab) or LLM drift (tighten prompt).
