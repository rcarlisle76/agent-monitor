import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import aiosqlite
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from database import ACCURACY_FLAG_THRESHOLD, get_db, init_db
from models import AgentResponse, MetricsResponse, ReportRequest, TaskRecord


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active_connections.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active_connections:
            self.active_connections.remove(ws)

    async def broadcast(self, message: dict):
        dead = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                dead.append(connection)
        for d in dead:
            self.active_connections.remove(d)


manager = ConnectionManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="Agent Monitor", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/report")
async def report(body: ReportRequest):
    metadata_str = json.dumps(body.metadata)
    flagged = (
        body.accuracy is not None and body.accuracy < ACCURACY_FLAG_THRESHOLD
    )

    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        await db.execute(
            """
            INSERT INTO agents (agent_id, parent_id, replaces, status, current_task, current_accuracy, flagged, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(agent_id) DO UPDATE SET
                parent_id = excluded.parent_id,
                status = excluded.status,
                current_task = excluded.current_task,
                current_accuracy = excluded.current_accuracy,
                flagged = CASE
                    WHEN excluded.current_accuracy IS NOT NULL
                    THEN excluded.flagged
                    ELSE agents.flagged
                END,
                metadata = excluded.metadata,
                last_updated = CURRENT_TIMESTAMP
            """,
            (body.agent_id, body.parent_id, body.replaces, body.status, body.task,
             body.accuracy, int(flagged), metadata_str),
        )
        await db.execute(
            "INSERT INTO tasks (agent_id, status, task, accuracy, metadata) VALUES (?, ?, ?, ?, ?)",
            (body.agent_id, body.status, body.task, body.accuracy, metadata_str),
        )
        await db.commit()

    payload = {
        "event": "agent_update",
        "agent_id": body.agent_id,
        "parent_id": body.parent_id,
        "replaces": body.replaces,
        "status": body.status,
        "task": body.task,
        "accuracy": body.accuracy,
        "flagged": flagged,
        "metadata": body.metadata,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    await manager.broadcast(payload)
    return {"ok": True, "flagged": flagged}


@app.get("/api/agents", response_model=list[AgentResponse])
async def list_agents():
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM agents ORDER BY last_updated DESC")
        rows = await cursor.fetchall()
    return [
        AgentResponse(
            agent_id=r["agent_id"],
            parent_id=r["parent_id"],
            replaces=r["replaces"],
            status=r["status"],
            current_task=r["current_task"],
            current_accuracy=r["current_accuracy"],
            flagged=bool(r["flagged"]),
            metadata=json.loads(r["metadata"] or "{}"),
            first_seen=r["first_seen"],
            last_updated=r["last_updated"],
        )
        for r in rows
    ]


@app.get("/api/agents/{agent_id}/history", response_model=list[TaskRecord])
async def agent_history(agent_id: str):
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM tasks WHERE agent_id = ? ORDER BY recorded_at DESC LIMIT 200",
            (agent_id,),
        )
        rows = await cursor.fetchall()
    return [
        TaskRecord(
            id=r["id"],
            agent_id=r["agent_id"],
            status=r["status"],
            task=r["task"],
            accuracy=r["accuracy"],
            metadata=json.loads(r["metadata"] or "{}"),
            recorded_at=r["recorded_at"],
        )
        for r in rows
    ]


@app.get("/api/metrics", response_model=MetricsResponse)
async def metrics():
    async with get_db() as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute(
            """
            SELECT
                COUNT(*) as total,
                SUM(status = 'running') as active,
                SUM(flagged = 1) as flagged
            FROM agents
            """
        )
        agent_row = await cursor.fetchone()

        cursor = await db.execute(
            "SELECT COUNT(*) as total, SUM(status = 'error') as errors FROM tasks"
        )
        task_row = await cursor.fetchone()

        cursor = await db.execute(
            """
            SELECT AVG((julianday(last_updated) - julianday(first_seen)) * 86400)
            FROM agents WHERE status = 'completed'
            """
        )
        dur_row = await cursor.fetchone()

        cursor = await db.execute(
            "SELECT AVG(accuracy) FROM tasks WHERE accuracy IS NOT NULL"
        )
        acc_row = await cursor.fetchone()

    total_tasks = task_row["total"] or 0
    error_count = int(task_row["errors"] or 0)
    error_rate = error_count / total_tasks if total_tasks > 0 else 0.0

    return MetricsResponse(
        active_agents=int(agent_row["active"] or 0),
        total_agents=int(agent_row["total"] or 0),
        total_tasks=total_tasks,
        flagged_agents=int(agent_row["flagged"] or 0),
        error_count=error_count,
        error_rate=error_rate,
        avg_accuracy=acc_row[0],
        avg_duration_seconds=dur_row[0],
    )


@app.get("/api/replacement-chains")
async def replacement_chains():
    async with get_db() as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute("SELECT * FROM agents ORDER BY first_seen ASC")
        agent_rows = await cursor.fetchall()

        # Last accuracy reading per agent (from task history)
        cursor = await db.execute("""
            SELECT t.agent_id, t.accuracy, t.recorded_at
            FROM tasks t
            INNER JOIN (
                SELECT agent_id, MAX(recorded_at) AS max_ts
                FROM tasks
                WHERE accuracy IS NOT NULL
                GROUP BY agent_id
            ) latest ON t.agent_id = latest.agent_id
                    AND t.recorded_at = latest.max_ts
        """)
        last_accuracy_rows = await cursor.fetchall()

    last_accuracy = {r["agent_id"]: r["accuracy"] for r in last_accuracy_rows}

    agents = {}
    for r in agent_rows:
        agents[r["agent_id"]] = {
            "agent_id": r["agent_id"],
            "status": r["status"],
            "current_accuracy": r["current_accuracy"],
            "flagged": bool(r["flagged"]),
            "first_seen": r["first_seen"],
            "last_updated": r["last_updated"],
            "replaces": r["replaces"],
            "last_accuracy": last_accuracy.get(r["agent_id"]),
        }

    # Build replaced_by map: original_id -> replacement_id
    replaced_by = {}
    for a in agents.values():
        if a["replaces"]:
            replaced_by[a["replaces"]] = a["agent_id"]

    # Find chain roots: agents that are not a replacement of anyone
    roots = [a for a in agents.values() if not a["replaces"]]

    chains = []
    for root in roots:
        # Only include roots that were either terminated or have replacements
        chain_members = []
        current = root
        while current:
            chain_members.append(current)
            next_id = replaced_by.get(current["agent_id"])
            current = agents.get(next_id)

        if len(chain_members) > 1 or chain_members[0]["status"] == "terminated":
            chains.append({
                "base_id": root["agent_id"],
                "chain": chain_members,
                "replacements": len(chain_members) - 1,
                "current": chain_members[-1],
            })

    # Sort: most replacements first
    chains.sort(key=lambda c: c["replacements"], reverse=True)
    return chains


@app.delete("/api/agents")
async def clear_all():
    async with get_db() as db:
        await db.execute("DELETE FROM tasks")
        await db.execute("DELETE FROM agents")
        await db.commit()
    await manager.broadcast({"event": "cleared"})
    return {"ok": True}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
