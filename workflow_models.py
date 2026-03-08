"""PlusFlow — domain models for workflow builder."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class NodeStatus(str, Enum):
    DRAFT = "draft"
    READY = "ready"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    BLOCKED = "blocked"
    DISABLED = "disabled"


class WorkflowStatus(str, Enum):
    DRAFT = "draft"
    RUNNING = "running"
    PARTIAL_SUCCESS = "partial_success"
    SUCCESS = "success"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Tool catalog
# ---------------------------------------------------------------------------
TOOL_CATALOG: list[dict[str, Any]] = [
    {
        "id": "input_parser",
        "name": "Input Parser",
        "description": "Parse raw input into structured data",
        "input_type": "text",
        "output_type": "structured",
    },
    {
        "id": "llm_generator",
        "name": "LLM Generator",
        "description": "Generate text using an LLM model",
        "input_type": "structured",
        "output_type": "text",
    },
    {
        "id": "summarizer",
        "name": "Summarizer",
        "description": "Summarize long text into key points",
        "input_type": "text",
        "output_type": "text",
    },
    {
        "id": "risk_extractor",
        "name": "Risk Extractor",
        "description": "Extract risks and concerns from text",
        "input_type": "text",
        "output_type": "structured",
    },
    {
        "id": "formatter",
        "name": "Formatter",
        "description": "Format data into a specific output template",
        "input_type": "structured",
        "output_type": "text",
    },
    {
        "id": "validator",
        "name": "Validator",
        "description": "Validate data against rules or schema",
        "input_type": "structured",
        "output_type": "structured",
    },
    {
        "id": "merger",
        "name": "Merger",
        "description": "Merge multiple inputs into one output",
        "input_type": "structured",
        "output_type": "structured",
    },
    {
        "id": "classifier",
        "name": "Classifier",
        "description": "Classify input into categories",
        "input_type": "text",
        "output_type": "structured",
    },
]


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Core data helpers  (plain dicts — easy to serialize)
# ---------------------------------------------------------------------------

def make_node(
    title: str,
    tool_id: str = "",
    description: str = "",
    parent_ids: list[str] | None = None,
) -> dict:
    return {
        "id": _uid(),
        "title": title,
        "description": description,
        "tool_id": tool_id,
        "parent_ids": parent_ids or [],
        "child_ids": [],
        "status": NodeStatus.DRAFT.value,
        "input_artifact_id": None,
        "output_artifact_id": None,
        "created_at": _now(),
        "updated_at": _now(),
    }


def make_artifact(name: str, producer_id: str, content: str = "") -> dict:
    return {
        "id": _uid(),
        "name": name,
        "producer_id": producer_id,
        "consumer_ids": [],
        "content": content,
        "preview": content[:200] if content else "",
        "created_at": _now(),
    }


def make_edge(from_id: str, to_id: str, artifact_id: str = "") -> dict:
    return {
        "id": _uid(),
        "from_id": from_id,
        "to_id": to_id,
        "artifact_id": artifact_id,
    }


def new_workflow(name: str = "Untitled Workflow") -> dict:
    return {
        "id": _uid(),
        "name": name,
        "status": WorkflowStatus.DRAFT.value,
        "nodes": {},
        "artifacts": {},
        "edges": [],
        "created_at": _now(),
        "updated_at": _now(),
    }


# ---------------------------------------------------------------------------
# DAG operations
# ---------------------------------------------------------------------------

def add_start_node(wf: dict, title: str, tool_id: str = "") -> str:
    node = make_node(title, tool_id=tool_id)
    wf["nodes"][node["id"]] = node
    wf["updated_at"] = _now()
    return node["id"]


def add_next_step(wf: dict, parent_id: str, title: str, tool_id: str = "") -> str:
    node = make_node(title, tool_id=tool_id, parent_ids=[parent_id])
    wf["nodes"][node["id"]] = node
    wf["nodes"][parent_id]["child_ids"].append(node["id"])
    edge = make_edge(parent_id, node["id"])
    wf["edges"].append(edge)
    wf["updated_at"] = _now()
    return node["id"]


def add_parallel_step(wf: dict, parent_id: str, title: str, tool_id: str = "") -> str:
    """Same as add_next_step — creates another child from the same parent."""
    return add_next_step(wf, parent_id, title, tool_id)


def delete_node(wf: dict, node_id: str) -> list[str]:
    """Delete a node and all its descendants. Returns list of deleted ids."""
    deleted: list[str] = []
    _collect_descendants(wf, node_id, deleted)
    for nid in deleted:
        node = wf["nodes"].pop(nid, None)
        if node:
            for pid in node["parent_ids"]:
                parent = wf["nodes"].get(pid)
                if parent and nid in parent["child_ids"]:
                    parent["child_ids"].remove(nid)
            # Remove artifacts
            for akey in ("input_artifact_id", "output_artifact_id"):
                aid = node.get(akey)
                if aid and aid in wf["artifacts"]:
                    del wf["artifacts"][aid]
    # Remove edges referencing deleted nodes
    wf["edges"] = [
        e for e in wf["edges"]
        if e["from_id"] not in deleted and e["to_id"] not in deleted
    ]
    wf["updated_at"] = _now()
    return deleted


def _collect_descendants(wf: dict, nid: str, acc: list[str]):
    acc.append(nid)
    node = wf["nodes"].get(nid)
    if node:
        for cid in list(node["child_ids"]):
            _collect_descendants(wf, cid, acc)


def _has_cycle(wf: dict) -> bool:
    visited: set[str] = set()
    rec_stack: set[str] = set()

    def dfs(nid: str) -> bool:
        visited.add(nid)
        rec_stack.add(nid)
        node = wf["nodes"].get(nid)
        if node:
            for cid in node["child_ids"]:
                if cid not in visited:
                    if dfs(cid):
                        return True
                elif cid in rec_stack:
                    return True
        rec_stack.discard(nid)
        return False

    for nid in wf["nodes"]:
        if nid not in visited:
            if dfs(nid):
                return True
    return False


def get_root_nodes(wf: dict) -> list[str]:
    return [nid for nid, n in wf["nodes"].items() if not n["parent_ids"]]


def get_levels(wf: dict) -> dict[str, int]:
    """Assign each node a level (depth) for rendering."""
    levels: dict[str, int] = {}
    roots = get_root_nodes(wf)
    queue = [(r, 0) for r in roots]
    while queue:
        nid, lvl = queue.pop(0)
        if nid in levels:
            levels[nid] = max(levels[nid], lvl)
        else:
            levels[nid] = lvl
        node = wf["nodes"].get(nid)
        if node:
            for cid in node["child_ids"]:
                queue.append((cid, lvl + 1))
    return levels


# ---------------------------------------------------------------------------
# Mock execution
# ---------------------------------------------------------------------------

def run_workflow(wf: dict) -> None:
    """Mock-execute the workflow following DAG order."""
    wf["status"] = WorkflowStatus.RUNNING.value
    levels = get_levels(wf)
    sorted_nodes = sorted(levels.keys(), key=lambda x: levels[x])

    all_ok = True
    for nid in sorted_nodes:
        node = wf["nodes"][nid]
        if node["status"] == NodeStatus.DISABLED.value:
            continue
        # Check parents are done
        parents_ok = all(
            wf["nodes"].get(pid, {}).get("status") == NodeStatus.SUCCESS.value
            for pid in node["parent_ids"]
        )
        if not parents_ok and node["parent_ids"]:
            node["status"] = NodeStatus.BLOCKED.value
            all_ok = False
            continue

        node["status"] = NodeStatus.RUNNING.value
        # Mock: create output artifact
        tool = _get_tool(node["tool_id"])
        tool_name = tool["name"] if tool else "Unknown"
        out_art = make_artifact(
            name=f"{node['title']} output",
            producer_id=nid,
            content=f"[Mock output from {tool_name}] Processed: {node['title']}",
        )
        wf["artifacts"][out_art["id"]] = out_art
        node["output_artifact_id"] = out_art["id"]

        # Wire input from parent output
        if node["parent_ids"]:
            parent = wf["nodes"].get(node["parent_ids"][0])
            if parent and parent.get("output_artifact_id"):
                node["input_artifact_id"] = parent["output_artifact_id"]
                art = wf["artifacts"].get(parent["output_artifact_id"])
                if art and nid not in art["consumer_ids"]:
                    art["consumer_ids"].append(nid)

        node["status"] = NodeStatus.SUCCESS.value
        node["updated_at"] = _now()

    wf["status"] = WorkflowStatus.SUCCESS.value if all_ok else WorkflowStatus.PARTIAL_SUCCESS.value
    wf["updated_at"] = _now()


def reset_workflow(wf: dict) -> None:
    """Reset all nodes to draft, clear artifacts."""
    for node in wf["nodes"].values():
        node["status"] = NodeStatus.DRAFT.value
        node["input_artifact_id"] = None
        node["output_artifact_id"] = None
    wf["artifacts"].clear()
    wf["status"] = WorkflowStatus.DRAFT.value
    wf["updated_at"] = _now()


def _get_tool(tool_id: str) -> dict | None:
    for t in TOOL_CATALOG:
        if t["id"] == tool_id:
            return t
    return None


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------
WORKFLOW_DIR = Path(__file__).parent / "workspace" / "workflows"
WORKFLOW_DIR.mkdir(parents=True, exist_ok=True)


def save_workflow(wf: dict) -> Path:
    path = WORKFLOW_DIR / f"{wf['id']}.json"
    path.write_text(json.dumps(wf, indent=2, ensure_ascii=False))
    return path


def load_workflow(wf_id: str) -> dict | None:
    path = WORKFLOW_DIR / f"{wf_id}.json"
    if path.exists():
        return json.loads(path.read_text())
    return None


def list_workflows() -> list[dict]:
    results = []
    for p in sorted(WORKFLOW_DIR.glob("*.json")):
        try:
            data = json.loads(p.read_text())
            results.append({"id": data["id"], "name": data["name"], "status": data["status"]})
        except Exception:
            continue
    return results


def delete_workflow_file(wf_id: str) -> None:
    path = WORKFLOW_DIR / f"{wf_id}.json"
    if path.exists():
        path.unlink()
