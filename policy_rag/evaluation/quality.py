"""Answer-quality run: what the assistant actually says, and where it is wrong.

Every question in ``ANSWER_QUALITY_SUITE`` goes through the same
``policy_rag.chat.service.answer`` call the web UI and the CLI use, so the
traces this produces are the real system's traces - just tagged with a run id
and with gold expectations attached so they can be labelled automatically.

The output is not a score. It is a ranked list of problem types
(frequency x severity) and a single prediction card naming the one change to
make next, what it should move, and what it will not fix. A score tells you
how you did; this tells you what to do.
"""

import time

from policy_rag import config
from policy_rag.evaluation.datasets import ANSWER_QUALITY_SUITE
from policy_rag.observability import taxonomy
from policy_rag.observability.traces import default_store, new_run_id

REPORT_NAME = "answer-quality.md"


def run_suite(
    region_override: str = None,
    hybrid: bool = None,
    top_k: int = None,
    progress: bool = True,
) -> dict:
    """Runs the full answer-quality suite through the live assistant.

    Args:
        region_override: Force every question to use this region filter,
            ignoring the per-question setting. Useful for focused debugging.
        hybrid: Retrieval mode. Defaults to ``config.DEFAULT_HYBRID``.
        top_k: Chunks retrieved per question.
        progress: Print one line per question as it completes.

    Returns:
        Dict with the ``run_id``, the labelled ``traces``, and ``stopped_early``
        naming why the run ended short when it did.
    """
    from policy_rag.chat.service import answer, is_quota_exhausted

    run_id = new_run_id("eval")
    traces = []
    stopped_early = None
    total = len(ANSWER_QUALITY_SUITE)

    for index, golden in enumerate(ANSWER_QUALITY_SUITE, start=1):
        region = region_override if region_override is not None else golden.region
        if progress:
            print(f"  [{index:02d}/{total}] {golden.id} | region={region or 'none'} | {golden.query[:52]}...")

        trace = answer(
            golden.query,
            region=region,
            top_k=top_k,
            hybrid=hybrid,
            run_id=run_id,
            source="evaluation",
            expectation=golden.expectation(),
            retries=config.EVAL_RETRIES,
        )
        traces.append(trace)

        if progress:
            print(f"          {trace['label']:<18} latency={trace['latency_ms']}ms")

        # A spent daily allowance is not a result. Continuing would record the
        # remaining questions as failures of the assistant when nothing was
        # ever asked of it, and would rank "pipeline error" as the top problem
        # to fix - which would be a lie about where the weakness is.
        if trace.get("error") and is_quota_exhausted(trace["error"]):
            stopped_early = (
                f"Daily API quota exhausted after {len(traces)} of {total} questions. "
                "The remaining questions were not asked."
            )
            if progress:
                print(f"\n  STOPPED: {stopped_early}")
            break

        # Stay inside the provider's requests-per-minute ceiling: a run that
        # trips the rate limiter measures the rate limiter, not the assistant.
        if index < total:
            time.sleep(config.EVAL_PAUSE_SECONDS)

    return {"run_id": run_id, "traces": traces, "stopped_early": stopped_early}


def build_report(traces: list, run_id: str = None, stopped_early: str = None) -> dict:
    """Turns labelled traces into a ranked taxonomy and a prediction card.

    Args:
        traces: Labelled traces from a suite run (or loaded from the log).
        run_id: The run these traces belong to.
        stopped_early: Why the run ended before the whole suite was asked, if
            it did. Carried into the report so a partial run is never read as
            a complete one.

    Returns:
        Dict with ``run_id``, ``traces``, ``taxonomy``, ``summary``,
        ``prediction``, ``coverage`` and ``stopped_early``.
    """
    ranked = taxonomy.build_taxonomy(traces)
    return {
        "run_id": run_id or (traces[0]["run_id"] if traces else None),
        "traces": traces,
        "taxonomy": ranked,
        "summary": taxonomy.summarise(traces),
        "prediction": taxonomy.prediction_card(ranked, len(traces)),
        "coverage": {"asked": len(traces), "suite": len(ANSWER_QUALITY_SUITE)},
        "stopped_early": stopped_early,
    }


def evaluate_answer_quality(
    region_override: str = None,
    hybrid: bool = None,
    top_k: int = None,
    progress: bool = True,
    write_report: bool = True,
) -> dict:
    """Runs the suite and builds the report.

    Args:
        region_override: Force a single region filter for every question.
        hybrid: Retrieval mode. Defaults to ``config.DEFAULT_HYBRID``.
        top_k: Chunks retrieved per question.
        progress: Print progress lines while running.
        write_report: Also write the Markdown report to ``config.REPORTS_DIR``.

    Returns:
        The report dict from ``build_report``, plus ``report_path`` when a
        Markdown report was written.
    """
    run = run_suite(region_override=region_override, hybrid=hybrid, top_k=top_k, progress=progress)
    report = build_report(run["traces"], run_id=run["run_id"], stopped_early=run["stopped_early"])
    if write_report:
        report["report_path"] = str(write_markdown_report(report))
    return report


def load_latest_report(run_id: str = None) -> dict:
    """Rebuilds the report from traces already on disk, making no LLM calls.

    Args:
        run_id: Specific run to load. Defaults to the most recent evaluation run.

    Returns:
        The report dict, with an empty trace list when nothing has been run yet.
    """
    traces = default_store.read(run_id=run_id) if run_id else default_store.latest_run(source="evaluation")
    return build_report(traces, run_id=run_id)


def write_markdown_report(report: dict, path=None):
    """Writes the report as Markdown.

    Args:
        report: Report dict from ``build_report``.
        path: Destination file. Defaults to ``config.REPORTS_DIR/answer-quality.md``.

    Returns:
        The path written to.
    """
    path = path or (config.REPORTS_DIR / REPORT_NAME)
    traces = report["traces"]
    coverage = report.get("coverage") or {"asked": len(traces), "suite": len(traces)}
    lines = [
        "# Answer Quality Report",
        "",
        f"Run: `{report['run_id']}`  ",
        f"Questions asked: {coverage['asked']} of {coverage['suite']}  ",
        f"Failures: {report['summary']['bugs']}  ",
        "",
        "Generated by `policy-rag eval quality`. Every trace below came from the "
        "same answer path the live assistant uses.",
        "",
    ]
    if report.get("stopped_early"):
        lines += [
            f"> **Partial run.** {report['stopped_early']} Read the numbers below as "
            "covering only the questions that were actually asked.",
            "",
        ]
    lines += [
        "## 1. Traces",
        "",
        "| ID | Label | Retrieval OK | Question | Observation |",
        "|---|---|---|---|---|",
    ]
    for trace in traces:
        query = trace["query"][:50].replace("|", "/")
        observation = trace["observation"][:110].replace("|", "/")
        identifier = trace.get("golden_id") or trace["trace_id"]
        lines.append(
            f"| {identifier} | {trace['label']} | {trace['retrieval_ok']} | {query} | {observation} |"
        )

    lines += ["", "## 2. Error Taxonomy", "", "Ranked by frequency x severity.", "",
              "| Priority | Category | Count | Severity | Score |", "|---|---|---|---|---|"]
    rank = 1
    for row in report["taxonomy"]:
        if row["severity"] == 0:
            priority = "-"
        else:
            priority = f"#{rank}"
            rank += 1
        lines.append(
            f"| {priority} | {row['display']} | {row['count']} | {row['severity']} | {row['score']} |"
        )

    prediction = report["prediction"]
    lines += ["", "## 3. Prediction Card", ""]
    if prediction:
        lines += [
            f"**Problem:** {prediction['display']} - {prediction['count']}/{prediction['total']} traces, "
            f"severity {prediction['severity']}/5, score {prediction['score']}",
            "",
            f"**Root cause:** {prediction['cause']}",
            "",
            f"**One change:** {prediction['change']}",
            "",
            f"**Prediction:** {prediction['prediction']}",
            "",
            f"**Will not fix:** {prediction['will_not_fix']}",
            "",
        ]
    else:
        lines += ["No failures in this run - every trace was a correct answer or a correct refusal.", ""]

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def print_report(report: dict) -> None:
    """Prints the report as a console report.

    Args:
        report: Report dict from ``build_report``.
    """
    rule = "=" * 74
    traces = report["traces"]

    print()
    print(rule)
    print("  1. TRACES - one honest observation each, written before the label")
    print(rule)
    for trace in traces:
        identifier = trace.get("golden_id") or trace["trace_id"]
        print(f"\n  {identifier}  [{trace['label']}]")
        print(f"    question  : {trace['query'][:64]}")
        print(f"    region    : {trace['region'] or '(none)'}")
        print(f"    refusal   : {trace['is_refusal']}   retrieval ok: {trace['retrieval_ok']}")
        print(f"    sources   : {', '.join(trace['top_sources']) or '(none)'}")
        print(f"    answer    : {trace['answer'][:110].replace(chr(10), ' ')}")
        print(f"    note      : {trace['observation']}")

    print()
    print(rule)
    print("  2. ERROR TAXONOMY - ranked by frequency x severity")
    print(rule)
    print(f"\n  {'Category':<46} {'Count':>5} {'Sev':>4} {'Score':>6}  Priority")
    print(f"  {'-' * 46} {'-' * 5} {'-' * 4} {'-' * 6}  --------")
    rank = 1
    for row in report["taxonomy"]:
        if row["severity"] == 0:
            priority = "(not a bug)"
        else:
            priority = f"#{rank}"
            rank += 1
        print(f"  {row['display']:<46} {row['count']:>5} {row['severity']:>4} {row['score']:>6}  {priority}")

    prediction = report["prediction"]
    print()
    print(rule)
    print("  3. PREDICTION CARD - the one change to make next")
    print(rule)
    if prediction is None:
        print("\n  No failures in this run - nothing to fix from this evidence.\n")
    else:
        print(f"\n  Problem      : {prediction['display']}")
        print(f"  Frequency    : {prediction['count']}/{prediction['total']} traces")
        print(f"  Severity     : {prediction['severity']}/5   Score: {prediction['score']}")
        print(f"\n  Root cause   : {prediction['cause']}")
        print(f"\n  One change   : {prediction['change']}")
        print(f"\n  Prediction   : {prediction['prediction']}")
        print(f"\n  Will not fix : {prediction['will_not_fix']}\n")

    summary = report["summary"]
    if report.get("stopped_early"):
        print(f"  PARTIAL RUN: {report['stopped_early']}")
    print(f"  SUMMARY: {summary['total']} traces | {summary['bugs']} failures | "
          f"{summary['ok']} correct or correct-refusal")
    if report.get("report_path"):
        print(f"  Report written to {report['report_path']}")
    print()


def main() -> None:
    """Runs the answer-quality suite from the command line."""
    import argparse

    parser = argparse.ArgumentParser(description="Answer-quality run: traces, taxonomy, prediction card")
    parser.add_argument("--from-traces", action="store_true",
                        help="rebuild the report from the stored traces instead of calling the LLM")
    parser.add_argument("--region", default=None, help="force one region filter for every question")
    args = parser.parse_args()

    if args.from_traces:
        report = load_latest_report()
        if not report["traces"]:
            print("No stored evaluation traces yet. Run without --from-traces first.")
            raise SystemExit(1)
    else:
        report = evaluate_answer_quality(region_override=args.region)
    print_report(report)


if __name__ == "__main__":
    main()
