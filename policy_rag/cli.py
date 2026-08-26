"""Command-line interface for the HR-207 policy assistant.

    policy-rag corpus                     regenerate the six addendum files
    policy-rag ingest [--keep]            build the vector index and docstore
    policy-rag chat                       interactive conversation
    policy-rag chat "question" [--json]   one question, one answer
    policy-rag serve [--port 8000]        run the web UI and API
    policy-rag traces [--limit N]         inspect the trace log
    policy-rag eval retrieval|chunking|quality|smoke

The same commands run as ``python -m policy_rag ...`` without installing.

Heavy dependencies are imported inside each command, so ``--help`` and the
lightweight commands stay instant instead of loading a 300 MB embedding model.
"""

import argparse
import json

from policy_rag import __version__, config


def cmd_corpus(args: argparse.Namespace) -> int:
    """Regenerates the corpus files under ``data/``."""
    from policy_rag.corpus.generator import write_corpus

    written = write_corpus()
    print(f"Wrote {len(written)} corpus files:")
    for path in written:
        print(f"  {path}")
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    """Builds the index, wiping the previous one unless ``--keep`` was passed."""
    from policy_rag.indexing import run_ingestion

    summary = run_ingestion(fresh=not args.keep)
    print(f"Summary: {summary}")
    return 0


def _print_envelope(envelope: dict) -> None:
    """Prints an answer with its retrieved chunks and observability block."""
    tokens = envelope.get("tokens") or {}
    print("\nANSWER")
    print("------")
    print(envelope["answer"])

    chunks = envelope.get("retrieved_chunks") or []
    print(f"\nSOURCES ({len(chunks)})")
    print("-------")
    for chunk in chunks:
        print(f"  [{chunk['rank']}] {chunk['source_file']}  region={chunk['region']}  score={chunk['score']}")

    print("\nPARAMETERS")
    print("----------")
    print(f"  region_filter : {envelope['region'] or '(none)'}")
    print(f"  top_k         : {envelope['top_k']}")
    print(f"  hybrid        : {envelope['hybrid']}")
    print(f"  is_refusal    : {envelope['is_refusal']}")
    print(f"  label         : {envelope['label']}")
    if envelope.get("standalone_query"):
        print(f"  rewritten as  : {envelope['standalone_query']}")
    print(f"  tokens        : prompt={tokens.get('prompt', 0)} completion={tokens.get('completion', 0)} "
          f"total={tokens.get('total', 0)} ({tokens.get('method', 'unavailable')})")
    print(f"  latency_ms    : {envelope['latency_ms']}")
    print(f"  llm_model     : {envelope['llm_model']}")
    print(f"  embed_model   : {envelope['embed_model']}")
    print(f"  trace_id      : {envelope['trace_id']}")
    if envelope.get("error"):
        print(f"  error         : {envelope['error']}")


def cmd_chat(args: argparse.Namespace) -> int:
    """Answers one question, or opens an interactive session when none is given."""
    from policy_rag.chat.session import ChatSession

    hybrid = None
    if args.hybrid:
        hybrid = True
    elif args.no_hybrid:
        hybrid = False

    session = ChatSession(region=args.region, top_k=args.top_k, hybrid=hybrid)

    if args.question:
        envelope = session.ask(args.question)
        if args.json:
            print(json.dumps(envelope, indent=2))
        else:
            _print_envelope(envelope)
        return 0

    return _interactive_chat(session, quiet=args.quiet)


def _interactive_chat(session, quiet: bool = False) -> int:
    """Runs the interactive chat loop.

    Args:
        session: The ``ChatSession`` to converse in.
        quiet: Print only answers, omitting sources and the parameter block.

    Returns:
        Process exit code.
    """
    print(f"HR-207 policy assistant {__version__}. Type a question, or:")
    print("  /region <CODE|none>   set the region filter    /reset   start a new conversation")
    print("  /sources              toggle the detail block  /exit    quit")
    print(f"Region: {session.region or '(none)'}   hybrid: "
          f"{config.DEFAULT_HYBRID if session.hybrid is None else session.hybrid}\n")

    show_detail = not quiet
    while True:
        try:
            message = input("you > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not message:
            continue
        if message in ("/exit", "/quit"):
            return 0
        if message == "/reset":
            session.reset()
            print("(conversation cleared)\n")
            continue
        if message == "/sources":
            show_detail = not show_detail
            print(f"(detail {'on' if show_detail else 'off'})\n")
            continue
        if message.startswith("/region"):
            parts = message.split()
            value = parts[1].upper() if len(parts) > 1 else "NONE"
            session.region = None if value in ("NONE", "ALL") else value
            print(f"(region filter: {session.region or 'none'})\n")
            continue

        envelope = session.ask(message)
        if show_detail:
            _print_envelope(envelope)
            print()
        else:
            print(f"\nbot > {envelope['answer']}\n")


def cmd_serve(args: argparse.Namespace) -> int:
    """Starts the web UI and JSON API."""
    from policy_rag.api.app import run

    host = args.host or config.API_HOST
    port = args.port or config.API_PORT
    print(f"Serving the policy assistant on http://{host}:{port}")
    run(host=host, port=port, reload=args.reload)
    return 0


def cmd_traces(args: argparse.Namespace) -> int:
    """Inspects, filters or clears the trace log."""
    from policy_rag.observability import taxonomy
    from policy_rag.observability.traces import default_store

    if args.clear:
        print(f"Removed {default_store.clear()} traces from {default_store.path}")
        return 0

    traces = default_store.read(limit=args.limit, source=args.source)
    if not traces:
        print(f"No traces recorded yet ({default_store.path}).")
        return 0

    if args.json:
        print(json.dumps(traces, indent=2))
        return 0

    print(f"{len(traces)} trace(s) from {default_store.path}\n")
    print(f"  {'ID':<14} {'LABEL':<20} {'REGION':<7} {'MS':>6}  QUESTION")
    print(f"  {'-' * 14} {'-' * 20} {'-' * 7} {'-' * 6}  {'-' * 40}")
    for trace in traces:
        identifier = trace.get("golden_id") or trace["trace_id"]
        print(f"  {identifier:<14} {trace['label']:<20} {(trace['region'] or '-'):<7} "
              f"{trace['latency_ms']:>6}  {trace['query'][:52]}")

    summary = taxonomy.summarise(traces)
    print(f"\n  {summary['total']} traces | {summary['bugs']} failures | {summary['ok']} clean")
    return 0


def cmd_eval_retrieval(args: argparse.Namespace) -> int:
    """Runs the retrieval benchmark."""
    from policy_rag.evaluation.retrieval import evaluate_retrieval, print_report

    print_report(evaluate_retrieval(top_k=args.top_k), verbose=args.verbose)
    return 0


def cmd_eval_chunking(args: argparse.Namespace) -> int:
    """Runs the chunking bake-off."""
    from policy_rag.evaluation.chunking import evaluate_chunking, print_report

    print_report(evaluate_chunking())
    return 0


def cmd_eval_quality(args: argparse.Namespace) -> int:
    """Runs the answer-quality suite, or rebuilds the last report from traces."""
    from policy_rag.evaluation.quality import (
        evaluate_answer_quality,
        load_latest_report,
        print_report,
    )

    if args.from_traces:
        report = load_latest_report()
        if not report["traces"]:
            print("No stored evaluation traces yet. Run without --from-traces first.")
            return 1
    else:
        print("Running the answer-quality suite: one LLM call per question.\n")
        report = evaluate_answer_quality(region_override=args.region, top_k=args.top_k)
    print_report(report)
    return 0


def cmd_eval_smoke(args: argparse.Namespace) -> int:
    """Runs the end-to-end smoke checks."""
    from policy_rag.evaluation.smoke import run_smoke_checks

    results = run_smoke_checks(verbose=True)
    return 0 if all(r["passed"] for r in results) else 1


def build_parser() -> argparse.ArgumentParser:
    """Builds the argument parser with every command.

    Returns:
        The configured ``ArgumentParser``.
    """
    parser = argparse.ArgumentParser(
        prog="policy-rag",
        description="HR-207 policy assistant: retrieval-augmented answers with citations.",
    )
    parser.add_argument("--version", action="version", version=f"policy-rag {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("corpus", help="regenerate the corpus files in data/") \
        .set_defaults(func=cmd_corpus)

    ingest = commands.add_parser("ingest", help="build the vector index and docstore")
    ingest.add_argument("--keep", action="store_true",
                        help="append to the existing index instead of rebuilding it")
    ingest.set_defaults(func=cmd_ingest)

    chat = commands.add_parser("chat", help="ask the assistant a question (interactive if omitted)")
    chat.add_argument("question", nargs="?", default=None, help="the question to ask")
    chat.add_argument("--region", default=None,
                      help=f"region filter ({', '.join(config.REGIONS)})")
    chat.add_argument("--top-k", type=int, default=None, dest="top_k",
                      help=f"chunks retrieved before auto-merging (default {config.DEFAULT_TOP_K})")
    chat.add_argument("--hybrid", action="store_true", help="force hybrid BM25 + vector retrieval")
    chat.add_argument("--no-hybrid", action="store_true", dest="no_hybrid",
                      help="force vector-only retrieval")
    chat.add_argument("--json", action="store_true", help="print the raw answer envelope as JSON")
    chat.add_argument("--quiet", action="store_true",
                      help="interactive mode: print answers only, no detail block")
    chat.set_defaults(func=cmd_chat)

    serve = commands.add_parser("serve", help="run the web UI and JSON API")
    serve.add_argument("--host", default=None, help=f"bind address (default {config.API_HOST})")
    serve.add_argument("--port", type=int, default=None, help=f"port (default {config.API_PORT})")
    serve.add_argument("--reload", action="store_true", help="auto-reload on code changes")
    serve.set_defaults(func=cmd_serve)

    traces = commands.add_parser("traces", help="inspect the trace log")
    traces.add_argument("--limit", type=int, default=25, help="how many recent traces to show")
    traces.add_argument("--source", default=None, choices=["chat", "evaluation"],
                        help="show only live chat traffic or only evaluation runs")
    traces.add_argument("--json", action="store_true", help="print raw trace JSON")
    traces.add_argument("--clear", action="store_true", help="delete every stored trace")
    traces.set_defaults(func=cmd_traces)

    evaluate = commands.add_parser("eval", help="run an evaluation suite")
    suites = evaluate.add_subparsers(dest="suite", required=True)

    retrieval = suites.add_parser("retrieval", help="vector-only vs hybrid: hit-rate@k and MRR")
    retrieval.add_argument("--top-k", type=int, default=None, dest="top_k")
    retrieval.add_argument("--verbose", "-v", action="store_true", help="print chunk previews")
    retrieval.set_defaults(func=cmd_eval_retrieval)

    suites.add_parser("chunking", help="naive vs structure-aware chunking: hit-in-top-5") \
        .set_defaults(func=cmd_eval_chunking)

    quality = suites.add_parser("quality", help="answer quality: traces, taxonomy, prediction card")
    quality.add_argument("--region", default=None, help="force one region filter for every question")
    quality.add_argument("--top-k", type=int, default=None, dest="top_k")
    quality.add_argument("--from-traces", action="store_true", dest="from_traces",
                         help="rebuild the report from stored traces instead of calling the LLM")
    quality.set_defaults(func=cmd_eval_quality)

    suites.add_parser("smoke", help="three end-to-end checks: refusal, region filter, edge case") \
        .set_defaults(func=cmd_eval_smoke)

    return parser


def main(argv: list = None) -> int:
    """Parses arguments and dispatches to the selected command.

    Args:
        argv: Argument list; defaults to ``sys.argv[1:]``.

    Returns:
        Process exit code.
    """
    config.ensure_runtime_dirs()
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
