"""
Demo agent simulation for the Agent Monitor dashboard.
Simulates an orchestrator coordinating worker agents processing documents.
The orchestrator monitors accuracy and terminates + replaces agents that drop below 70%.

Usage:
    python demo_agents.py
    python demo_agents.py --url http://localhost:3000  (default)
    python demo_agents.py --workers 4
    python demo_agents.py --workers 4 --docs 10
"""

import argparse
import random
import time
import urllib.error
import urllib.request
import json
import threading

DOCS = [
    "Q1 Financial Report.pdf",
    "Customer Feedback Survey.xlsx",
    "Product Roadmap 2026.docx",
    "Security Audit Results.pdf",
    "Market Analysis EMEA.pptx",
    "Employee Handbook v3.docx",
    "Bug Report Batch #447.csv",
    "Legal Contract Draft.pdf",
    "Architecture Diagram.png",
    "Release Notes v2.1.md",
    "Sales Pipeline Q2.xlsx",
    "Compliance Checklist.docx",
    "Infrastructure Cost Report.pdf",
    "User Research Synthesis.docx",
    "API Documentation v4.pdf",
]

WORKER_TASKS = [
    "Extracting text",
    "Running OCR",
    "Chunking content",
    "Generating embeddings",
    "Classifying document",
    "Summarizing content",
    "Checking compliance",
    "Indexing to vector store",
    "Writing output",
]

ACCURACY_THRESHOLD = 70.0


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def post(url, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{url}/api/report",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read())
    except urllib.error.URLError as e:
        print(f"  [warn] POST failed: {e.reason}")
        return {}


def report(url, agent_id, status, task=None, parent_id=None, metadata=None, accuracy=None, replaces=None):
    payload = {
        "agent_id": agent_id,
        "status": status,
        "task": task,
        "parent_id": parent_id,
        "metadata": metadata or {},
    }
    if accuracy is not None:
        payload["accuracy"] = round(accuracy, 2)
    if replaces is not None:
        payload["replaces"] = replaces
    result = post(url, payload)

    badge = {"running": ">", "idle": "o", "completed": "+", "error": "X", "terminated": "-"}.get(status, "?")
    acc_str = f" [{accuracy:.1f}%{'!' if accuracy < ACCURACY_THRESHOLD else ''}]" if accuracy is not None else ""
    print(f"  {badge} [{agent_id}]{acc_str} {status}: {task or ''}")
    return result


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------

class Worker:
    def __init__(self, worker_id, parent_id, docs_queue, url,
                 stop_event, flagged_callback, base_accuracy_mean=82):
        self.worker_id = worker_id
        self.parent_id = parent_id
        self.docs_queue = docs_queue   # list used as a shared queue (pop from front)
        self.docs_lock = threading.Lock()
        self.url = url
        self.stop_event = stop_event   # set by orchestrator to terminate this worker
        self.flagged_callback = flagged_callback  # called when this worker gets flagged
        self.base_accuracy_mean = base_accuracy_mean
        self.current_accuracy = None
        self.thread = None

    def start(self, replaces=None):
        report(self.url, self.worker_id, "idle", "Waiting for assignments",
               parent_id=self.parent_id, replaces=replaces)
        time.sleep(random.uniform(0.2, 0.6))
        self.thread = threading.Thread(target=self._run, args=(replaces,), daemon=True)
        self.thread.start()

    def join(self):
        if self.thread:
            self.thread.join()

    def _run(self, replaces):
        base = random.gauss(mu=self.base_accuracy_mean, sigma=10)
        base = max(40.0, min(99.0, base))
        step_accuracy = base

        while not self.stop_event.is_set():
            doc = self._next_doc()
            if doc is None:
                break

            report(self.url, self.worker_id, "running", f"Received: {doc}",
                   parent_id=self.parent_id)
            time.sleep(random.uniform(0.4, 1.0))

            steps = random.sample(WORKER_TASKS, k=random.randint(3, 6))
            flagged = False

            for step in steps:
                if self.stop_event.is_set():
                    return

                step_accuracy += random.gauss(mu=0, sigma=5)
                step_accuracy = max(30.0, min(99.0, step_accuracy))
                self.current_accuracy = step_accuracy

                result = report(
                    self.url, self.worker_id, "running",
                    f"{step} — {doc}",
                    parent_id=self.parent_id,
                    accuracy=step_accuracy,
                    metadata={"document": doc, "step": step},
                )

                if result.get("flagged") and not flagged:
                    flagged = True
                    self.flagged_callback(self.worker_id, step_accuracy, doc)

                time.sleep(random.uniform(0.7, 2.0))

                if self.stop_event.is_set():
                    return

            if self.stop_event.is_set():
                return

            final_accuracy = max(30.0, min(99.0, step_accuracy + random.gauss(0, 3)))
            report(
                self.url, self.worker_id, "completed", f"Done: {doc}",
                parent_id=self.parent_id,
                accuracy=final_accuracy,
                metadata={"document": doc,
                          "pages_processed": random.randint(1, 80),
                          "final_accuracy": round(final_accuracy, 2)},
            )
            time.sleep(random.uniform(0.3, 0.8))

        if not self.stop_event.is_set():
            report(self.url, self.worker_id, "idle", "No more documents",
                   parent_id=self.parent_id)

    def _next_doc(self):
        return self.docs_queue.pop(0) if self.docs_queue else None


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class Orchestrator:
    def __init__(self, url, num_workers, docs):
        self.url = url
        self.num_workers = num_workers
        self.docs = list(docs)          # shared queue (mutated by workers)
        self.docs_lock = threading.Lock()
        self.workers: dict[str, Worker] = {}
        self.stop_events: dict[str, threading.Event] = {}
        self.replacement_counters: dict[str, int] = {}  # worker_id -> generation
        self.lock = threading.Lock()
        self.all_done = threading.Event()

    def run(self):
        report(self.url, "orchestrator", "running",
               f"Starting pipeline: {len(self.docs)} docs across {self.num_workers} workers")
        time.sleep(0.8)

        # Spin up initial workers
        worker_ids = [f"worker-{i+1}" for i in range(self.num_workers)]
        for wid in worker_ids:
            self.replacement_counters[wid] = 0
            self._spawn_worker(wid, replaces=None)
            time.sleep(random.uniform(0.2, 0.5))

        # Wait for all workers to finish
        while True:
            time.sleep(1.0)
            with self.lock:
                active = [w for w in self.workers.values()
                          if w.thread and w.thread.is_alive()]
                if not active and not self.docs:
                    break

        # Final summary
        total = len(DOCS[:self.num_workers * 5])  # rough
        report(self.url, "orchestrator", "completed",
               f"Pipeline complete — all documents processed",
               metadata={"total_docs": len(self.docs)})

    def _spawn_worker(self, base_id, replaces=None, boosted=False):
        """Create and start a worker. boosted=True gives it a higher accuracy mean."""
        gen = self.replacement_counters.get(base_id, 0)
        worker_id = base_id if gen == 0 else f"{base_id}-v{gen+1}"
        stop_event = threading.Event()

        accuracy_mean = 90 if boosted else 82  # replacements get a boost

        worker = Worker(
            worker_id=worker_id,
            parent_id="orchestrator",
            docs_queue=self.docs,
            url=self.url,
            stop_event=stop_event,
            flagged_callback=self._on_flagged,
            base_accuracy_mean=accuracy_mean,
        )
        with self.lock:
            self.workers[worker_id] = worker
            self.stop_events[worker_id] = stop_event

        worker.start(replaces=replaces)
        return worker_id

    def _on_flagged(self, worker_id, accuracy, current_doc):
        """Called by a worker thread when the backend flags it."""
        # Run the response in its own thread so the worker thread isn't blocked
        threading.Thread(
            target=self._handle_termination,
            args=(worker_id, accuracy, current_doc),
            daemon=True,
        ).start()

    def _handle_termination(self, worker_id, accuracy, current_doc):
        with self.lock:
            # Guard: only terminate once per worker
            stop_event = self.stop_events.get(worker_id)
            if stop_event is None or stop_event.is_set():
                return
            stop_event.set()

        print(f"\n  [!] ORCHESTRATOR: {worker_id} accuracy={accuracy:.1f}% -- initiating termination\n")

        # Orchestrator announces its decision
        time.sleep(0.5)
        report(
            self.url, "orchestrator", "running",
            f"Low accuracy detected on {worker_id} ({accuracy:.1f}%) — terminating",
            metadata={
                "action": "terminate",
                "target": worker_id,
                "accuracy": round(accuracy, 2),
                "threshold": ACCURACY_THRESHOLD,
            },
        )
        time.sleep(0.8)

        # Mark the worker as terminated
        report(
            self.url, worker_id, "terminated",
            f"Terminated by orchestrator — accuracy {accuracy:.1f}% below {ACCURACY_THRESHOLD}%",
            parent_id="orchestrator",
            accuracy=accuracy,
            metadata={"reason": "low_accuracy", "terminated_by": "orchestrator"},
        )
        time.sleep(0.5)

        # Derive the base name for replacement (strip -vN suffix)
        base_id = worker_id.split("-v")[0] if "-v" in worker_id else worker_id
        with self.lock:
            self.replacement_counters[base_id] = self.replacement_counters.get(base_id, 0) + 1
            gen = self.replacement_counters[base_id]

        replacement_id = f"{base_id}-v{gen+1}"
        report(
            self.url, "orchestrator", "running",
            f"Spawning replacement {replacement_id} for {worker_id}",
            metadata={
                "action": "replace",
                "terminated": worker_id,
                "replacement": replacement_id,
            },
        )
        time.sleep(0.5)

        # Spawn the replacement with boosted accuracy
        new_id = self._spawn_worker(base_id, replaces=worker_id, boosted=True)
        print(f"\n  [+] ORCHESTRATOR: spawned {new_id} to replace {worker_id}\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:3000")
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--docs", type=int, default=len(DOCS),
                        help=f"Number of documents to process (max {len(DOCS)})")
    args = parser.parse_args()

    docs = random.sample(DOCS, min(args.docs, len(DOCS)))

    print(f"\nAgent Monitor Demo")
    print(f"  Dashboard  : {args.url}")
    print(f"  Workers    : {args.workers}")
    print(f"  Documents  : {len(docs)}")
    print(f"  Flag at    : accuracy < {ACCURACY_THRESHOLD}%")
    print(f"\nStarting...\n")

    orch = Orchestrator(url=args.url, num_workers=args.workers, docs=docs)
    orch.run()

    print("\nDone! Check the dashboard at", args.url)


if __name__ == "__main__":
    main()
