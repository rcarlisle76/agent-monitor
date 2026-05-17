"""
Agent Monitor Client
====================
Drop this file into any Python project to report agent activity
to the Agent Monitor dashboard.

Quickstart:
    from agent_monitor_client import AgentMonitor

    monitor = AgentMonitor("http://your-host:3000")

    monitor.running("my-agent", "Processing batch 1")
    # ... do work ...
    monitor.completed("my-agent", accuracy=94.2)

For hierarchical agents:
    monitor.running("orchestrator", "Coordinating pipeline")
    monitor.running("worker-1", "Summarising doc A", parent_id="orchestrator")
"""

import json
import threading
import urllib.error
import urllib.request
from typing import Literal

Status = Literal["running", "idle", "completed", "error", "terminated"]


class AgentMonitor:
    """
    Thread-safe client for reporting agent status to the Agent Monitor dashboard.

    Args:
        base_url: Root URL of the dashboard, e.g. "http://localhost:3000"
        default_parent_id: Optional parent agent to attach all reports to by default.
        timeout: HTTP timeout in seconds (default 5).
        silent: If True, swallow connection errors instead of printing them.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:3000",
        default_parent_id: str | None = None,
        timeout: int = 5,
        silent: bool = False,
    ):
        self.base_url = base_url.rstrip("/")
        self.default_parent_id = default_parent_id
        self.timeout = timeout
        self.silent = silent
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Convenience methods
    # ------------------------------------------------------------------

    def running(
        self,
        agent_id: str,
        task: str | None = None,
        *,
        parent_id: str | None = None,
        accuracy: float | None = None,
        replaces: str | None = None,
        metadata: dict | None = None,
    ):
        """Report that an agent is actively working on a task."""
        return self.report(agent_id, "running", task,
                           parent_id=parent_id, accuracy=accuracy,
                           replaces=replaces, metadata=metadata)

    def idle(
        self,
        agent_id: str,
        task: str | None = None,
        *,
        parent_id: str | None = None,
        metadata: dict | None = None,
    ):
        """Report that an agent is waiting for work."""
        return self.report(agent_id, "idle", task,
                           parent_id=parent_id, metadata=metadata)

    def completed(
        self,
        agent_id: str,
        task: str | None = None,
        *,
        parent_id: str | None = None,
        accuracy: float | None = None,
        metadata: dict | None = None,
    ):
        """Report that an agent has successfully finished."""
        return self.report(agent_id, "completed", task,
                           parent_id=parent_id, accuracy=accuracy,
                           metadata=metadata)

    def error(
        self,
        agent_id: str,
        task: str | None = None,
        *,
        parent_id: str | None = None,
        accuracy: float | None = None,
        error_message: str | None = None,
        metadata: dict | None = None,
    ):
        """Report that an agent encountered an error."""
        meta = dict(metadata or {})
        if error_message:
            meta["error"] = error_message
        return self.report(agent_id, "error", task,
                           parent_id=parent_id, accuracy=accuracy,
                           metadata=meta)

    def terminated(
        self,
        agent_id: str,
        *,
        parent_id: str | None = None,
        accuracy: float | None = None,
        reason: str | None = None,
        metadata: dict | None = None,
    ):
        """Report that an agent was terminated (e.g. by an orchestrator)."""
        meta = dict(metadata or {})
        if reason:
            meta["reason"] = reason
        return self.report(agent_id, "terminated", None,
                           parent_id=parent_id, accuracy=accuracy,
                           metadata=meta)

    # ------------------------------------------------------------------
    # Core method
    # ------------------------------------------------------------------

    def report(
        self,
        agent_id: str,
        status: Status,
        task: str | None = None,
        *,
        parent_id: str | None = None,
        accuracy: float | None = None,
        replaces: str | None = None,
        metadata: dict | None = None,
    ) -> dict:
        """
        Send a status report for any agent.

        Returns the parsed JSON response, or {} on failure.

        Args:
            agent_id:   Unique identifier for this agent.
            status:     One of: running, idle, completed, error, terminated.
            task:       Human-readable description of the current task.
            parent_id:  ID of the parent/orchestrator agent, if any.
            accuracy:   Float 0–100. Values below the dashboard threshold
                        (default 70) will flag the agent for termination.
            replaces:   ID of the agent this one was spawned to replace.
            metadata:   Arbitrary dict of extra data to attach.
        """
        payload: dict = {
            "agent_id": agent_id,
            "status": status,
            "task": task,
            "parent_id": parent_id or self.default_parent_id,
            "metadata": metadata or {},
        }
        if accuracy is not None:
            payload["accuracy"] = round(float(accuracy), 4)
        if replaces is not None:
            payload["replaces"] = replaces

        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            f"{self.base_url}/api/report",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self._lock:
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return json.loads(resp.read())
            except Exception as exc:
                if not self.silent:
                    print(f"[AgentMonitor] warning: could not reach dashboard — {exc}")
                return {}

    # ------------------------------------------------------------------
    # Context manager — automatically reports idle on exit
    # ------------------------------------------------------------------

    def agent(
        self,
        agent_id: str,
        *,
        parent_id: str | None = None,
        replaces: str | None = None,
    ) -> "AgentSession":
        """
        Context manager for a single agent session.

            with monitor.agent("worker-1", parent_id="orchestrator") as agent:
                agent.running("Step 1", accuracy=88.0)
                agent.running("Step 2", accuracy=91.5)
            # automatically reports idle on exit
        """
        return AgentSession(self, agent_id,
                            parent_id=parent_id, replaces=replaces)


class AgentSession:
    """Returned by AgentMonitor.agent(). Scopes calls to one agent_id."""

    def __init__(self, monitor: AgentMonitor, agent_id: str,
                 parent_id: str | None, replaces: str | None):
        self._monitor = monitor
        self._agent_id = agent_id
        self._parent_id = parent_id
        self._replaces = replaces

    def __enter__(self):
        self._monitor.idle(self._agent_id, parent_id=self._parent_id)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self._monitor.error(self._agent_id,
                                error_message=str(exc_val),
                                parent_id=self._parent_id)
        else:
            self._monitor.idle(self._agent_id, "Session ended",
                               parent_id=self._parent_id)
        return False  # don't suppress exceptions

    def running(self, task: str, *, accuracy: float | None = None, metadata: dict | None = None):
        return self._monitor.running(self._agent_id, task,
                                     parent_id=self._parent_id,
                                     accuracy=accuracy,
                                     replaces=self._replaces,
                                     metadata=metadata)

    def completed(self, task: str | None = None, *, accuracy: float | None = None, metadata: dict | None = None):
        return self._monitor.completed(self._agent_id, task,
                                       parent_id=self._parent_id,
                                       accuracy=accuracy, metadata=metadata)

    def error(self, task: str | None = None, *, error_message: str | None = None, metadata: dict | None = None):
        return self._monitor.error(self._agent_id, task,
                                   parent_id=self._parent_id,
                                   error_message=error_message,
                                   metadata=metadata)

    def report(self, status: Status, task: str | None = None, **kwargs):
        return self._monitor.report(self._agent_id, status, task,
                                    parent_id=self._parent_id, **kwargs)
