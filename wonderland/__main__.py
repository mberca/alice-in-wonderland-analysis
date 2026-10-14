"""Run with python -m wonderland; all analysis is local and deterministic."""

import argparse
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

from .analysis import analyse, write_csv, write_outputs
from .core import concordance, load_book
from .mapreduce import decode_pairs, encode_pair, map_characters, mapreduce_counts, reduce_sorted
from .site import render_story

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "data" / "alice-gutenberg-11.txt"


def project_book(source):
    book = load_book(source)
    provenance = json.loads((ROOT / "data" / "provenance.json").read_text(encoding="utf-8"))
    if book.source_sha256 != provenance["sha256"]:
        raise ValueError("Source checksum differs from the pinned edition in data/provenance.json.")
    return book


def build(args):
    book = project_book(args.source)
    result, evidence = analyse(book)
    page = render_story(result, evidence, ROOT / "web" / "story.html")
    if args.check:
        with TemporaryDirectory() as folder:
            write_outputs(result, folder)
            (Path(folder) / "PROJECT_GUTENBERG_LICENSE.txt").write_text(
                book.license_text + "\n", encoding="utf-8", newline="\n")
            for generated in Path(folder).iterdir():
                committed = args.output / generated.name
                if not committed.is_file() or generated.read_bytes() != committed.read_bytes():
                    raise ValueError(f"Generated evidence is stale or missing: {committed.name}")
        if not args.site.is_file() or args.site.read_bytes() != page.encode("utf-8"):
            raise ValueError("The browser story is stale or missing; run the build command.")
        print("All generated evidence and the browser story match a fresh build.")
        return
    write_outputs(result, args.output)
    (args.output / "PROJECT_GUTENBERG_LICENSE.txt").write_text(
        book.license_text + "\n", encoding="utf-8", newline="\n")
    args.site.parent.mkdir(parents=True, exist_ok=True)
    args.site.write_text(page, encoding="utf-8", newline="\n")
    print(f"Built {result['summary']['words']:,} word tokens across 12 chapters.")
    print(f"Legacy exercise: {result['legacy_reproduction']}")
    print(f"Modern narrative counts: { {k: result['target_totals'][k] for k in ('Alice', 'Rabbit')} }")
    print(f"Evidence: {args.output}\nBrowser story: {args.site}")


def query(args):
    matches = concordance(project_book(args.source), args.term, chapter=args.chapter,
                          ignore_case=not args.exact, possessives=args.possessives)
    print(json.dumps({"term": args.term, "count": len(matches), "matches": matches[:args.limit]},
                     ensure_ascii=False, indent=2))


def character_analysis(args):
    book = project_book(args.source)
    text = book.narrative if args.scope == "narrative" else book.source_text
    counts = mapreduce_counts(text, chunk_size=args.chunk_size,
                             letters_only=not args.all_characters, ignore_case=not args.exact)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        write_csv(args.output, [{"character": key, "count": value} for key, value in counts.items()],
                  ("character", "count"))
    else:
        for pair in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
            print(encode_pair(pair))


def streaming(args):
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    if args.command == "mapper":
        for line in sys.stdin:
            for pair in map_characters(line, letters_only=not args.all_characters,
                                       ignore_case=not args.exact):
                print(encode_pair(pair))
    elif args.command == "shuffle":
        # Teaching-only local sort; a distributed engine supplies this phase at scale.
        for pair in sorted(decode_pairs(sys.stdin), key=lambda pair: pair[0]):
            print(encode_pair(pair))
    else:
        for pair in reduce_sorted(decode_pairs(sys.stdin)):
            print(encode_pair(pair))


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m wonderland",
                                     description="Wonderland, Measured: a reproducible literary-data lab.")
    commands = parser.add_subparsers(dest="command", required=True)
    build_parser = commands.add_parser("build", help="Rebuild evidence and the offline browser story.")
    build_parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    build_parser.add_argument("--output", type=Path, default=ROOT / "outputs")
    build_parser.add_argument("--site", type=Path, default=ROOT / "docs" / "index.html")
    build_parser.add_argument("--check", action="store_true", help="Fail if committed outputs are stale.")
    build_parser.set_defaults(run=build)
    query_parser = commands.add_parser("query", help="Find literal word occurrences with source context.")
    query_parser.add_argument("term")
    query_parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    query_parser.add_argument("--chapter", type=int, choices=range(1, 13))
    query_parser.add_argument("--exact", action="store_true", help="Match case.")
    query_parser.add_argument("--possessives", action="store_true", help="Also group final 's forms.")
    query_parser.add_argument("--limit", type=int, default=20)
    query_parser.set_defaults(run=query)
    mr = commands.add_parser("mapreduce", help="Run a local partitioned character-count pipeline.")
    mr.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    mr.add_argument("--scope", choices=("narrative", "full_source"), default="narrative")
    mr.add_argument("--chunk-size", type=int, default=4096)
    mr.add_argument("--all-characters", action="store_true")
    mr.add_argument("--exact", action="store_true")
    mr.add_argument("--output", type=Path)
    mr.set_defaults(run=character_analysis)
    for name in ("mapper", "shuffle", "reducer"):
        sub = commands.add_parser(name, help=f"JSON-lines streaming {name}; UTF-8 stdin/stdout.")
        if name == "mapper":
            sub.add_argument("--all-characters", action="store_true")
            sub.add_argument("--exact", action="store_true")
        sub.set_defaults(run=streaming)
    args = parser.parse_args(argv)
    if getattr(args, "limit", 1) < 1:
        parser.error("--limit must be positive.")
    try:
        args.run(args)
    except (OSError, UnicodeError, ValueError) as error:
        parser.exit(2, f"error: {error}\n")


if __name__ == "__main__":
    main()
