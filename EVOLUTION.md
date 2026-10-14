# From the original exercise to the showcase

This project grows from Margarita Bermejo Cano's 2013/14 programming report.
The private report itself is not published: it contains academic identifiers
and screenshots unrelated to the public text-analysis code.

## What remains recognisable

The original Alice section asked how often the names `Alice` and `Rabbit`
occurred. A Python program opened a text file, removed selected punctuation,
accumulated a dictionary of counts, and printed the result.

A separate Alice section explored MapReduce with Python mapper/reducer
programs and AWS/Hadoop streaming. It reported character frequencies rather
than word frequencies.

Both questions remain first-class parts of the rebuilt project. The two
tasks are not confused with one another or replaced by an unrelated model.

## What changed and why

| Original approach | Rebuilt approach | Why it matters |
|---|---|---|
| Python 2 `dict.has_key` | Python 3, `Counter`, explicit matching functions | Current, runnable code with readable responsibilities. |
| A function called `getSentences` returned file lines | Explicit chapter bodies and token offsets | Lines are formatting, not sentences; misleading units disappear. |
| File opened without a context manager; I/O failure returned an empty list | `Path` input and explicit nonzero CLI errors | A missing file cannot masquerade as a successful zero count. |
| A few punctuation marks removed globally | Documented Unicode token boundaries | Quotes, apostrophes, compounds, and case become deliberate decisions. |
| A count without pinned source identity | Original bytes, checksum, edition metadata, licence | Another person can reproduce this particular result. |
| Full file treated as the analysis text | Narrative and original-file scopes are separate | Chapter headings and legal text do not silently become the novel. |
| Two whole-book totals | Chapter rates, frequencies, TF–IDF, MATTR, concordance | Patterns can be inspected and checked against the source. |
| Manual screenshots of output | Deterministic JSON/CSV exports and a generated browser story | Evidence can be regenerated rather than trusted as a picture. |
| A cloud cluster for a small text | Local MapReduce stages and direct-counter equivalence tests | Keep the programming lesson without unnecessary infrastructure. |
| Historical output accepted as reported | Separate reproduced, redefined, and unreproduced results | A showcase demonstrates analytical honesty as well as coding. |

## Preserve the original answer

The legacy word counter reproduces **Alice = 377** and **Rabbit = 40** from
the supplied file. Modernisation does not erase that successful result.
The story shows how modern, chapter-only definitions produce different
answers, without relabelling them as the original method's result.

The report also describes an early surprise: searching for lowercase `rabbit`
returned **2**, before the query was changed to capitalised `Rabbit` and
returned **40**. Both case-sensitive results reproduce under the original
full-file rules. The story preserves that learning moment as **“A capital
discovery”**, with figures computed from the source rather than typed into
the page.

The report's **`e` = 15,394** character result remains explicitly
**unreproduced** from this source under literal lowercase counting.
Possible explanations require evidence about the original input and mapper;
they are not asserted as facts.

## What is deliberately not added

There is no unvalidated sentiment dashboard, invented character network,
dialogue attribution, author identification, causal interpretation, or LLM
summary presented as measured evidence. A sophisticated-looking exhibit is
not an improvement if its analytical basis cannot be defended.

The emphasis is **measurement design, reusable programming, reproducibility,
and communication**—a substantive progression from the original exercise.
