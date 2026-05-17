"""
Research Pipeline — Claude Agent Demo
======================================
An orchestrator Claude agent breaks a topic into challenging subtopics.
Worker Claude agents process each subtopic through three stages:
  1. Research   — write a detailed summary
  2. Fact-check — identify and verify specific claims
  3. Analysis   — draw conclusions and implications

Each stage is graded independently by a strict grader agent.
Workers whose rolling accuracy drops below 70% are flagged, terminated,
and replaced by a new worker that picks up the remaining subtopics.

The orchestrator compiles all findings into a final report.

Usage:
    python research_pipeline.py
    python research_pipeline.py --topic "climate change" --workers 3
    python research_pipeline.py --topic "the Roman Empire" --workers 4

Requirements:
    pip install anthropic
    Set ANTHROPIC_API_KEY in your environment.

Output:
    reports/<topic>/worker-1.md, worker-2.md, ...
    reports/<topic>/final_report.md
"""

import argparse
import re
import threading
import time
from pathlib import Path

import anthropic

from agent_monitor_client import AgentMonitor

client = anthropic.Anthropic()
monitor = AgentMonitor("http://localhost:3000")

_results_lock = threading.Lock()
_worker_results: dict[str, dict] = {}


def claude(prompt: str, max_tokens: int = 1000) -> str:
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text.strip()


def strict_grade(stage: str, subtopic: str, content: str) -> float:
    """
    Strict grader that penalises vague claims, missing specifics,
    and shallow reasoning. Returns 0-100.
    """
    criteria = {
        "research": (
            "- Contains specific facts (dates, figures, names, or events): up to 40 pts\n"
            "- Accurate and relevant to the subtopic: up to 35 pts\n"
            "- Clear and well-structured: up to 25 pts\n"
            "- Deduct 15-25 pts for factual errors or major omissions"
        ),
        "fact-check": (
            "- Identifies the key claims from the research: up to 40 pts\n"
            "- Correctly assesses each claim as verified, questionable, or incorrect: up to 35 pts\n"
            "- Provides useful corrections or caveats: up to 25 pts\n"
            "- Deduct 15-20 pts if fact-check is superficial or misses obvious issues"
        ),
        "analysis": (
            "- Draws conclusions that go beyond restating the research: up to 40 pts\n"
            "- Discusses implications or significance: up to 35 pts\n"
            "- Analytical depth and originality: up to 25 pts\n"
            "- Deduct 15-20 pts for generic or circular analysis"
        ),
    }

    rubric = criteria.get(stage, "- Be fair but thorough")
    raw = claude(
        f"You are an academic reviewer grading a {stage} output on '{subtopic}'.\n\n"
        f"Scoring rubric:\n{rubric}\n\n"
        f"Content to grade:\n{content}\n\n"
        f"Calibration guide:\n"
        f"- 85-100: Excellent, specific, insightful\n"
        f"- 70-84:  Good, mostly accurate with minor gaps\n"
        f"- 55-69:  Mediocre, vague or missing key facts\n"
        f"- Below 55: Poor, inaccurate or very superficial\n\n"
        f"Most outputs should score in the 65-82 range. "
        f"Give below 65 only when clearly warranted.\n"
        f"Reply with a single integer score 0-100. No explanation."
    )
    match = re.search(r"\d+(?:\.\d+)?", raw)
    return min(100.0, max(0.0, float(match.group()))) if match else 60.0


def process_subtopic(worker_id: str, subtopic: str) -> dict | None:
    """
    Run a subtopic through three stages. Returns findings dict or None if flagged.
    Each stage score is reported to the dashboard.
    """
    scores = []

    # --- Stage 1: Research ---
    monitor.running(worker_id, f"[Research] {subtopic}", parent_id="orchestrator")
    print(f"    [{worker_id}] Research: {subtopic}")
    research = claude(
        f"Write a detailed research summary about the following specific subtopic.\n"
        f"You MUST include at least 3 specific facts with dates, figures, or names.\n"
        f"Do not be vague. Subtopic: {subtopic}"
    )
    r_score = strict_grade("research", subtopic, research)
    scores.append(r_score)
    avg = sum(scores) / len(scores)
    print(f"    [{worker_id}] Research score: {r_score:.1f}%")

    result = monitor.running(
        worker_id, f"[Research done] {subtopic}",
        parent_id="orchestrator", accuracy=avg,
    )
    if result.get("flagged"):
        return None

    # --- Stage 2: Fact-check ---
    monitor.running(worker_id, f"[Fact-check] {subtopic}", parent_id="orchestrator", accuracy=avg)
    print(f"    [{worker_id}] Fact-checking: {subtopic}")
    fact_check = claude(
        f"You are a fact-checker. Review the research below about '{subtopic}'.\n"
        f"List each specific claim, then state whether it is: verified, questionable, or incorrect.\n"
        f"For questionable or incorrect claims, provide the correct information.\n\n"
        f"Research:\n{research}"
    )
    fc_score = strict_grade("fact-check", subtopic, fact_check)
    scores.append(fc_score)
    avg = sum(scores) / len(scores)
    print(f"    [{worker_id}] Fact-check score: {fc_score:.1f}%")

    result = monitor.running(
        worker_id, f"[Fact-check done] {subtopic}",
        parent_id="orchestrator", accuracy=avg,
    )
    if result.get("flagged"):
        return None

    # --- Stage 3: Analysis ---
    monitor.running(worker_id, f"[Analysis] {subtopic}", parent_id="orchestrator", accuracy=avg)
    print(f"    [{worker_id}] Analysing: {subtopic}")
    analysis = claude(
        f"Based on the research and fact-check below about '{subtopic}', "
        f"write a critical analysis.\n"
        f"Draw non-obvious conclusions. Discuss broader implications and significance.\n"
        f"Do NOT simply restate the research — add genuine analytical insight.\n\n"
        f"Research:\n{research}\n\nFact-check:\n{fact_check}"
    )
    a_score = strict_grade("analysis", subtopic, analysis)
    scores.append(a_score)
    avg = sum(scores) / len(scores)
    print(f"    [{worker_id}] Analysis score: {a_score:.1f}%  (subtopic avg: {avg:.1f}%)")

    result = monitor.running(
        worker_id, f"[Analysis done] {subtopic}",
        parent_id="orchestrator", accuracy=avg,
    )
    if result.get("flagged"):
        return None

    time.sleep(0.2)
    return {
        "subtopic": subtopic,
        "research": research,
        "fact_check": fact_check,
        "analysis": analysis,
        "scores": {"research": r_score, "fact_check": fc_score, "analysis": a_score},
        "avg": avg,
    }


def run_worker(
    worker_id: str,
    subtopics: list,
    reports_dir: Path,
    replaces: str | None = None,
) -> None:
    monitor.running(
        worker_id,
        f"Starting — {len(subtopics)} subtopics assigned",
        parent_id="orchestrator",
        replaces=replaces,
    )
    print(f"\n  [{worker_id}] Starting — {len(subtopics)} subtopics")

    findings = []
    all_scores = []

    for i, subtopic in enumerate(subtopics):
        print(f"\n  [{worker_id}] Subtopic {i + 1}/{len(subtopics)}: {subtopic}")
        result = process_subtopic(worker_id, subtopic)

        if result is None:
            # Worker was flagged mid-subtopic
            print(f"  [{worker_id}] FLAGGED during '{subtopic}' — terminating")
            monitor.terminated(worker_id, reason="low_accuracy")
            replacement_id = f"{worker_id}-v2"
            remaining = subtopics[i + 1:]
            if remaining:
                run_worker(replacement_id, remaining, reports_dir, replaces=worker_id)
            return

        findings.append(result)
        all_scores.extend(result["scores"].values())
        rolling_avg = sum(all_scores) / len(all_scores)

        # Report rolling average after each completed subtopic
        flagged_result = monitor.running(
            worker_id,
            f"Completed {i + 1}/{len(subtopics)} subtopics",
            parent_id="orchestrator",
            accuracy=rolling_avg,
        )

        if flagged_result.get("flagged"):
            print(f"  [{worker_id}] FLAGGED after subtopic — terminating")
            monitor.terminated(worker_id, reason="low_accuracy")
            replacement_id = f"{worker_id}-v2"
            remaining = subtopics[i + 1:]
            if remaining:
                run_worker(replacement_id, remaining, reports_dir, replaces=worker_id)
            return

    # Write worker report
    final_acc = sum(all_scores) / len(all_scores) if all_scores else 0.0
    monitor.running(worker_id, "Writing report", parent_id="orchestrator", accuracy=final_acc)
    print(f"\n  [{worker_id}] Writing report...")

    report_path = reports_dir / f"{worker_id}.md"
    lines = [f"# {worker_id} Research Report\n", f"**Final accuracy: {final_acc:.1f}%**\n", "---\n"]
    for f in findings:
        lines += [
            f"## {f['subtopic']}\n",
            f"### Research *(score: {f['scores']['research']:.1f}%)*\n{f['research']}\n",
            f"### Fact-check *(score: {f['scores']['fact_check']:.1f}%)*\n{f['fact_check']}\n",
            f"### Analysis *(score: {f['scores']['analysis']:.1f}%)*\n{f['analysis']}\n",
            "---\n",
        ]
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  [{worker_id}] Report saved: {report_path}")

    with _results_lock:
        _worker_results[worker_id] = {"findings": findings, "accuracy": final_acc}

    monitor.completed(worker_id, accuracy=final_acc)
    print(f"  [{worker_id}] Done. Final accuracy: {final_acc:.1f}%")


def main(topic: str, num_workers: int) -> None:
    safe_topic = re.sub(r"[^\w\s-]", "", topic).strip().replace(" ", "_").lower()
    reports_dir = Path("reports") / safe_topic
    reports_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nTopic    : {topic}")
    print(f"Workers  : {num_workers}")
    print(f"Reports  : {reports_dir}/")
    print(f"Dashboard: http://localhost:3000\n")

    monitor.running("orchestrator", f"Planning research on: {topic}")

    # Generate a mix of accessible and challenging subtopics
    print("Orchestrator: generating subtopics...")
    raw = claude(
        f"List {num_workers * 3} subtopics to research about '{topic}'.\n"
        f"Mix difficulty: some broad and well-known, some specific and technical.\n"
        f"About one third should be obscure or require precise dates and figures.\n"
        f"One subtopic per line. No numbering, no bullets, no extra text."
    )
    subtopics = [s.strip() for s in raw.splitlines() if s.strip()][: num_workers * 3]
    print(f"Orchestrator: {len(subtopics)} subtopics assigned\n")
    for s in subtopics:
        print(f"  - {s}")

    monitor.running(
        "orchestrator",
        f"Assigning {len(subtopics)} subtopics across {num_workers} workers",
    )

    # Distribute and run workers in parallel
    threads = []
    for i in range(num_workers):
        worker_id = f"worker-{i + 1}"
        assigned = subtopics[i::num_workers]
        t = threading.Thread(
            target=run_worker,
            args=(worker_id, assigned, reports_dir),
            daemon=True,
        )
        threads.append(t)

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Orchestrator compiles final report
    print("\nOrchestrator: compiling final report...")
    monitor.running("orchestrator", "Compiling final report")

    all_content = []
    for worker_id, data in sorted(_worker_results.items()):
        for f in data["findings"]:
            all_content.append(
                f"Subtopic: {f['subtopic']}\n"
                f"Research: {f['research']}\n"
                f"Analysis: {f['analysis']}"
            )

    executive_summary = ""
    if all_content:
        combined = "\n\n---\n\n".join(all_content)
        executive_summary = claude(
            f"You are a senior editor compiling a final research report on '{topic}'.\n"
            f"Based on the worker findings below, write a cohesive executive summary (4-5 paragraphs).\n"
            f"Synthesise key findings, highlight significant insights, and note any contradictions.\n\n"
            f"{combined}",
            max_tokens=1500,
        )

    final_path = reports_dir / "final_report.md"
    lines = [
        f"# Research Report: {topic}\n",
        f"*Workers: {num_workers} | Subtopics: {len(subtopics)}*\n",
        "## Executive Summary\n",
        executive_summary or "*No findings compiled.*",
        "\n---\n",
        "## Worker Summary\n",
    ]
    for worker_id, data in sorted(_worker_results.items()):
        lines.append(f"- **{worker_id}**: {len(data['findings'])} subtopics, avg accuracy {data['accuracy']:.1f}%")

    lines += ["\n---\n", "## Detailed Findings\n"]
    for worker_id, data in sorted(_worker_results.items()):
        lines.append(f"### {worker_id} (avg: {data['accuracy']:.1f}%)\n")
        for f in data["findings"]:
            scores = f["scores"]
            lines.append(
                f"#### {f['subtopic']}\n"
                f"*Research: {scores['research']:.0f}% | "
                f"Fact-check: {scores['fact_check']:.0f}% | "
                f"Analysis: {scores['analysis']:.0f}%*\n\n"
                f"{f['research']}\n"
            )

    final_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Orchestrator: final report saved: {final_path}")

    monitor.completed("orchestrator", "Final report compiled")
    print(f"\nDone! Reports in {reports_dir}/")
    print("Check the dashboard for the full agent run.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Claude research pipeline")
    parser.add_argument("--topic", default="space exploration", help="Topic to research")
    parser.add_argument("--workers", type=int, default=3, help="Number of worker agents")
    args = parser.parse_args()
    main(args.topic, args.workers)
