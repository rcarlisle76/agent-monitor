# Agent Monitor — Integration Guide

## 1. Start the dashboard

```cmd
docker compose -f docker-compose.deploy.yml up
```

Open **http://localhost:3000** — that's the dashboard.  
Your agents report to **http://localhost:3000/api/report**.

---

## 2. Configuration (edit docker-compose.deploy.yml)

| Environment variable | Default | What it does |
|---|---|---|
| `ACCURACY_FLAG_THRESHOLD` | `70.0` | Agents below this accuracy % get flagged for termination |

Change the port by editing `"3000:80"` → e.g. `"8080:80"` in the compose file.

---

## 3. API contract

**POST** `http://<host>:<port>/api/report`

```json
{
  "agent_id":  "worker-1",
  "status":    "running",
  "task":      "Summarising document A",
  "parent_id": "orchestrator",
  "replaces":  null,
  "accuracy":  87.4,
  "metadata":  {}
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `agent_id` | string | yes | Unique ID for this agent |
| `status` | string | yes | `running` `idle` `completed` `error` `terminated` |
| `task` | string | no | What the agent is doing right now |
| `parent_id` | string | no | ID of the parent/orchestrator agent |
| `replaces` | string | no | ID of the agent this one was spawned to replace |
| `accuracy` | float 0–100 | no | Triggers a flag if below threshold |
| `metadata` | object | no | Any extra key/value data |

**Response**
```json
{ "ok": true, "flagged": false }
```
`flagged: true` means this agent's accuracy dropped below the threshold — your orchestrator should act on this.

---

## 4. Python — using the included client

Copy `agent_monitor_client.py` into your project. No pip install needed.

```python
from agent_monitor_client import AgentMonitor

monitor = AgentMonitor("http://localhost:3000")

# Simple calls
monitor.running("my-agent", "Step 1: loading data")
monitor.running("my-agent", "Step 2: processing", accuracy=91.2)
monitor.completed("my-agent", accuracy=88.5)

# With a parent (hierarchical)
monitor.running("orchestrator", "Starting pipeline")
monitor.running("worker-1", "Chunk 1", parent_id="orchestrator", accuracy=85.0)

# Context manager — auto-reports idle on exit, error on exception
with monitor.agent("worker-2", parent_id="orchestrator") as agent:
    agent.running("Loading model", accuracy=90.0)
    agent.running("Running inference", accuracy=78.3)
    agent.completed(accuracy=82.1)

# Check if the dashboard flagged you (accuracy too low)
result = monitor.running("worker-3", "Step 1", accuracy=61.0)
if result.get("flagged"):
    print("Orchestrator should replace this agent")
```

---

## 5. Python — raw requests (no client file needed)

```python
import requests

MONITOR = "http://localhost:3000"

def report(agent_id, status, task=None, **kwargs):
    requests.post(f"{MONITOR}/api/report", json={
        "agent_id": agent_id,
        "status": status,
        "task": task,
        **kwargs
    }, timeout=5)

report("my-agent", "running", "Processing batch", accuracy=88.0, parent_id="orchestrator")
report("my-agent", "completed", accuracy=91.5)
```

---

## 6. JavaScript / Node.js

```js
const MONITOR = "http://localhost:3000";

async function report(agentId, status, task, opts = {}) {
  await fetch(`${MONITOR}/api/report`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ agent_id: agentId, status, task, ...opts }),
  });
}

await report("my-agent", "running", "Step 1", { parent_id: "orchestrator", accuracy: 88.0 });
await report("my-agent", "completed", null, { accuracy: 91.5 });
```

---

## 7. Shell / curl

```bash
# Running
curl -s -X POST http://localhost:3000/api/report \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"my-agent","status":"running","task":"Step 1","accuracy":88.0}'

# Completed
curl -s -X POST http://localhost:3000/api/report \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"my-agent","status":"completed","accuracy":91.5}'
```

**Windows cmd:**
```cmd
curl -s -X POST http://localhost:3000/api/report -H "Content-Type: application/json" -d "{\"agent_id\":\"my-agent\",\"status\":\"running\",\"task\":\"Step 1\",\"accuracy\":88.0}"
```

---

## 8. Building a self-managing orchestrator

The dashboard flags agents but doesn't terminate them — that decision belongs to your orchestrator. Pattern:

```python
from agent_monitor_client import AgentMonitor

monitor = AgentMonitor("http://localhost:3000")

def run_worker(worker_id, task, parent_id):
    result = monitor.running(worker_id, task,
                             parent_id=parent_id, accuracy=compute_accuracy())
    if result.get("flagged"):
        # Tell the dashboard this agent is done
        monitor.terminated(worker_id, parent_id=parent_id,
                           accuracy=compute_accuracy(),
                           reason="low_accuracy")
        # Spawn a replacement
        replacement_id = f"{worker_id}-v2"
        monitor.running(replacement_id, "Taking over",
                        parent_id=parent_id, replaces=worker_id)
        # ... start replacement logic ...
```

---

## 9. Connecting agents on other machines

If the dashboard is running on a remote server, replace `localhost` with the server's IP or hostname:

```python
monitor = AgentMonitor("http://192.168.1.50:3000")
```

Make sure port `3000` is reachable from the agent's machine (firewall, VPC, etc.).
