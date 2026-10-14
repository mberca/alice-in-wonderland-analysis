# Source text and provenance

`alice-gutenberg-11.txt` is the user-supplied **Project Gutenberg eBook #11**
edition of Lewis Carroll's *Alice's Adventures in Wonderland*.

- Edition: **The Millennium Fulcrum Edition 3.0**.
- Header release: March 1994; posting: June 25, 2008; last update:
  December 20, 2011.
- Source catalogue: <https://www.gutenberg.org/ebooks/11>.
- Byte size: **167,512**.
- SHA-256:
  `0fc5533d17050c71c49dab56c54adcc1cdda1d10c15e0ab2f2b68df10c538ed4`.
- Acquisition: an existing local copy, retained **byte-for-byte**. The
  current file on Gutenberg may be a different edition; a fresh download
  is not assumed to be identical.

The book is committed so a normal analysis needs no network or account.
Git attributes mark this one source file `-text`, preventing Git from
rewriting its original line-ending bytes. Analysis separately normalises
line endings and Unicode; that never changes the retained input.

`provenance.json` is the machine-readable record. CLI analysis rejects a
checksum mismatch instead of silently combining a changed source with old
edition metadata.

## Rights and redistribution

Lewis Carroll's original 1865 novel is public domain in the United States.
The supplied Gutenberg edition has its own licence/trademark terms, which
remain attached in full. Check applicable law outside the United States.
The application's MIT licence does **not** replace those terms.

This eBook is for the use of anyone anywhere at no cost and with almost no
restrictions whatsoever. You may copy it, give it away or re-use it under
the terms of the Project Gutenberg License included with this eBook or
online at <https://www.gutenberg.org>.

The full licence appears at the end of the unmodified source and is also
included in `outputs/PROJECT_GUTENBERG_LICENSE.txt` and the generated offline
story. The story provides a download of the exact original source bytes.
Keep those notices and the original text together when redistributing.

## Analysis boundary

Only the **bodies of chapters I–XII** enter narrative measures.
The title page, chapter headings, final `THE END`, Gutenberg end credit,
and licence are excluded from that corpus. They remain available in the
full-file comparison and legacy reproduction.

No academic report, student identifier, cloud configuration, or user
history is part of this data directory.
