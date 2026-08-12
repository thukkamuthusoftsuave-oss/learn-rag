"""Command-line interface for the HR-207 RAG pipeline.

Primary entry point for the whole workflow:

- ``python cli.py setup-data`` — regenerate the 6 regional addendum files.
- ``python cli.py ingest [--keep]`` — build the vector index + docstore
  (wipes existing stores first unless ``--keep`` is passed).
- ``python cli.py query "<question>" [--region R] [--top-k N] [--json]`` —
  ask a question; prints the answer plus a PARAMETERS observability block
  (top-k, token usage, latency, retrieved chunks, models). ``--json`` prints
  the raw envelope instead.
- ``python cli.py eval`` — offline chunker evaluation (TF-IDF hit-in-top-5).
- ``python cli.py verify`` — end-to-end smoke checks (refusal, region
  filtering, bonus scenario).

Heavy dependencies (llama_index et al.) are imported lazily inside each
subcommand so ``--help`` and lightweight commands stay fast.
"""

import argparse
import json


def cmd_setup_data(args: argparse.Namespace) -> int:
    """Regenerates the corpus from ``setup_data.py``.

    Args:
        args: Parsed CLI arguments (unused by this command).

    Returns:
        Process exit code.
    """
    from setup_data import main as setup_main
    setup_main()
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    """Runs ingestion, fresh unless ``--keep`` was passed.

    Args:
        args: Parsed CLI arguments; uses ``args.keep``.

    Returns:
        Process exit code.
    """
    from ingest import run_ingestion
    summary = run_ingestion(fresh=not args.keep)
    print(f"Summary: {summary}")
    return 0


def cmd_query(args: argparse.Namespace) -> int:
    """Answers a question and prints the observability envelope.

    Args:
        args: Parsed CLI arguments; uses ``args.query``, ``args.region``,
            ``args.top_k`` and ``args.json``.

    Returns:
        Process exit code.
    """
    from retriever import query_rag
    envelope = query_rag(args.query, region=args.region, top_k=args.top_k, detailed=True)

    if args.json:
        print(json.dumps(envelope, indent=2))
        return 0

    tokens = envelope["tokens"]
    print("ANSWER")
    print("------")
    print(envelope["answer"])
    print()
    print("PARAMETERS")
    print("----------")
    print(f"region_filter : {envelope['region'] or '(none)'}")
    print(f"top_k         : {envelope['top_k']}")
    print(f"is_refusal    : {envelope['is_refusal']}")
    print(f"tokens        : prompt={tokens['prompt']} completion={tokens['completion']} "
          f"total={tokens['total']} ({tokens['method']})")
    print(f"latency_ms    : {envelope['latency_ms']}")
    print(f"llm_model     : {envelope['llm_model']}")
    print(f"embed_model   : {envelope['embed_model']}")
    print(f"timestamp     : {envelope['timestamp']}")
    chunks = envelope["retrieved_chunks"]
    print(f"retrieved_chunks ({len(chunks)}):")
    for i, chunk in enumerate(chunks, 1):
        print(f"  [{i}] score={chunk['score']} source={chunk['source_file']} node={chunk['node_id']}")
    return 0


def cmd_eval(args: argparse.Namespace) -> int:
    """Runs the offline chunker evaluation.

    Args:
        args: Parsed CLI arguments (unused by this command).

    Returns:
        Process exit code.
    """
    from eval import run_evaluation
    run_evaluation(verbose=True)
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    """Runs the end-to-end verification scenarios.

    Args:
        args: Parsed CLI arguments (unused by this command).

    Returns:
        Process exit code.
    """
    from verify import run_verification
    run_verification(verbose=True)
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Builds the CLI argument parser with all subcommands.

    Returns:
        The configured ``ArgumentParser``.
    """
    parser = argparse.ArgumentParser(
        prog="rag",
        description="HR-207 policy RAG pipeline CLI",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("setup-data", help="regenerate the 6 addendum files")\
        .set_defaults(func=cmd_setup_data)

    ingest_parser = subparsers.add_parser("ingest", help="build the vector index and docstore")
    ingest_parser.add_argument("--keep", action="store_true",
                               help="append to existing stores instead of wiping first")
    ingest_parser.set_defaults(func=cmd_ingest)

    query_parser = subparsers.add_parser("query", help="ask a question against the corpus")
    query_parser.add_argument("query", help="natural-language question")
    query_parser.add_argument("--region", default=None,
                              help="region metadata filter (NA, EMEA, APAC, LATAM, US, UK)")
    query_parser.add_argument("--top-k", type=int, default=5, dest="top_k",
                              help="number of leaf chunks retrieved before auto-merging (default: 5)")
    query_parser.add_argument("--json", action="store_true",
                              help="print the raw observability envelope as JSON")
    query_parser.set_defaults(func=cmd_query)

    subparsers.add_parser("eval", help="run the chunker evaluation")\
        .set_defaults(func=cmd_eval)

    subparsers.add_parser("verify", help="run end-to-end smoke checks")\
        .set_defaults(func=cmd_verify)

    return parser


def main(argv: list = None) -> int:
    """Parses CLI arguments and dispatches to the subcommand handler.

    Args:
        argv: Optional argument list (defaults to ``sys.argv[1:]``).

    Returns:
        Process exit code from the subcommand handler.
    """
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
