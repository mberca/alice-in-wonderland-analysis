# Measurement contract

## Purpose and unit of analysis

This is a descriptive, single-book text-analysis project, not a model of
literature or a predictive ML benchmark. It preserves the original word-count
and character-count questions while making each measurement reproducible.

The primary unit is a **word token inside a narrative chapter body**. A word
form is the token after the stated case/apostrophe normalisation. A chapter is
not an input-file line, a sentence, or an independent random observation.

## Source and corpus boundary

`data/provenance.json` pins the SHA-256 and byte size of the supplied Gutenberg
edition. The input is copied byte-for-byte, including its full licence.
Analysis decodes UTF-8 (accepting a UTF-8 BOM), normalises line endings to LF
and Unicode to NFC, and requires one ordered Gutenberg START/END marker pair.

Exactly twelve unique, ordered `CHAPTER I.` through `CHAPTER XII.` headings
must be present. Only their bodies enter narrative measures. Front matter,
chapter titles, the final `THE END`, the end-of-ebook credit, and the legal
footer do not. An uncertain boundary is an error, not permission to analyse
the whole file as a substitute.

The original-file view is explicitly different: it includes source metadata
and legal text. It uses the same decoded and normalised text, not raw bytes.
No source is downloaded during a normal run.

## Tokenisation and matching

The Unicode regex is:

```text
[^\W\d_]+(?:['’-][^\W\d_]+)*
```

Numbers, punctuation, and surrounding quotation marks are not tokens.
Internal apostrophes and single hyphens remain inside a token. Thus
`Alice's`, `rabbit-hole`, and `don't` each form one token. An em dash or a
double hyphen separates tokens. No abbreviation-aware sentence splitting is
used, and line breaks are not labelled as sentences.

Curly apostrophes are matched equivalently to straight apostrophes.
The three modern matching policies are:

1. **Exact:** preserve case; match the complete token.
2. **Folded:** Unicode case-fold; match the complete token.
3. **Possessive grouping:** case-fold, then mechanically remove one final
   `'s` from both the query and candidate token.

The third policy is not full lemmatisation or grammatical classification.
For arbitrary words, a final `'s` may be a contraction rather than possession.
Only the explicitly selected rule determines whether it is grouped.
Name cues are not named-entity recognition. A literal `rabbit` can be an
ordinary animal; mentions such as `she`, aliases, and descriptions are not
resolved to characters.

The CLI supports these rules for Unicode tokens. Browser matching is designed
for this English corpus; it uses NFC, apostrophe normalisation, lowercasing,
and the `ß → ss` mapping rather than claiming universal Unicode case-fold
equivalence for every possible language.

## Faithful legacy comparison

The supplied Python 2 code removes only `"!.,;:&?`, splits on whitespace,
and counts exactly `Alice` and `Rabbit`. Apostrophes and hyphens are not
removed. It reads the whole file.

`legacy_counts` reproduces those semantics in Python 3. Its output is **377 /
40**, matching the original report. This historical view is kept separate
from chapter-only modern tokenisation. Differences can reflect both the
corpus boundary and matching rules; they are not all attributable to case.

The report's initial lowercase `rabbit` search also reproduces: **2**, versus
**40** for `Rabbit` under exactly the same legacy rules and full-file scope.
`legacy_case_comparison` computes these two counts for the story's “A capital
discovery” feature. They are deliberately separate from chapter-only modern
token counts; the feature does not use the browser's case-folded search total.

## Frequency and normalisation

Raw counts are integers. A chapter rate is:

```text
matching occurrences / all narrative word tokens in that chapter × 1,000
```

The denominator is not the filtered content-word count. Chapter maxima use
unrounded values; ties are resolved by chapter order. A higher raw count may
occur in a different chapter from the higher normalised rate.

The content-word exhibit excludes `STOPWORDS` in `wonderland/core.py` and forms
shorter than three characters, without stemming. The list is a small,
hand-specified English function-word filter. It is not a semantic importance
model. `said` is intentionally not suppressed.

## Chapter TF–IDF

Each chapter is a document; the twelve chapters are the complete comparison
collection. For a candidate form:

```text
TF = chapter occurrences / all chapter tokens
IDF = log((1 + 12) / (1 + number of chapters containing the form)) + 1
score = TF × IDF
```

Candidates pass the same content-word filter and occur at least three times
within the chapter. Display the top five, sorting score ties alphabetically.
Scores are deterministic weights, **not** probabilities, p-values, character
identities, or evidence of importance to the story.

## Moving-average type/token ratio

MATTR-100 is the average of:

```text
distinct case-folded word forms in a 100-token window / 100
```

Move the window by one token. The measure is unavailable below 100 tokens;
short chapters do not silently receive another window size. Whole-book MATTR
uses the concatenated chapter token sequence, so its windows can cross chapter
boundaries. Chapter scores do not.

Use the same window size for comparisons. The overlapping windows are not
independent observations. No confidence intervals or significance claims are
attached. The exhibit is not a readability, sophistication, or quality score.

## Character counting and local MapReduce

The default maps case-folded Unicode letters to `(character, 1)`, combines
within 4,096-character input chunks, groups keys locally, and sums them with
a sorted reducer. Chunk boundaries precede case-folding; a multi-character
case-fold expansion such as `ß → ss` contributes both resulting characters.
Tests establish equality to a direct counter across chunk sizes.

`--exact` preserves case; `--all-characters` includes whitespace, punctuation,
and symbols. These settings are independent. A literal lowercase `e` count is
not the same quantity as a case-folded `e/E` count. The browser letter
distribution always uses the default case-folded-letter definition.

The separate streaming stages use JSON lines to preserve whitespace and
special-character keys. The reducer fails on invalid pairs or unsorted
keys. The local shuffle sorts in memory. This is an educational local
implementation, not a claim of distributed execution, large-scale throughput,
or bounded-memory processing for arbitrarily large inputs.

The original report's **15,394** `e` count is retained as a historical claim.
It does not reproduce as a literal lowercase count from this pinned source
(**15,081** full-file / **13,358** narrative). The original mapper settings or
exact MapReduce input would be needed to reconcile it. No post hoc processing
is chosen to force the historical value.

## Evidence and reproducibility

The browser concordance indexes the same token occurrences used by the
analysis. Its spans use UTF-16 code units so JavaScript slices correctly even
when a non-BMP character appears earlier in a chapter. Queries and result
passages enter the DOM as text, not executable HTML.

The browser includes the full edition licence and can download the exact
original bytes. All figures are local computations; no LLM or external API
produces scores or receives search terms.

Generated outputs use deterministic sorting, fixed precision where rounded,
UTF-8, and LF line endings. `build --check` compares a fresh build with
committed evidence. Tests cover corpus boundaries, source identity, original
results, counting policies, source-position reconstruction, numerical
definitions, local MapReduce equivalence, malformed inputs, CLI errors, and
HTML data embedding.
