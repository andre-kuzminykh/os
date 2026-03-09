"""PlusFlow v0.2 — hierarchical task board models."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
STATUSES = ["To Do", "In Progress", "Done"]

STATUS_ICONS = {
    "To Do": "⬜",
    "In Progress": "🔶",
    "Done": "✅",
}


TOOLS = [
    {"id": "input_parser", "name": "Input Parser", "description": "Parse raw input into structured data"},
    {"id": "llm_generator", "name": "LLM Generator", "description": "Generate text using an LLM"},
    {"id": "summarizer", "name": "Summarizer", "description": "Summarize long text into key points"},
    {"id": "risk_extractor", "name": "Risk Extractor", "description": "Extract risks from text"},
    {"id": "formatter", "name": "Formatter", "description": "Format data into a template"},
    {"id": "validator", "name": "Validator", "description": "Validate data against rules"},
    {"id": "merger", "name": "Merger", "description": "Merge multiple inputs into one"},
    {"id": "classifier", "name": "Classifier", "description": "Classify input into categories"},
    {"id": "translator", "name": "Translator", "description": "Translate text between languages"},
    {"id": "code_generator", "name": "Code Generator", "description": "Generate code from spec"},
]

TOOL_NAMES = ["(no tool)"] + [t["name"] for t in TOOLS]

MODELS = ["GPT-4o", "GPT-4o mini", "Claude Sonnet", "Claude Haiku"]


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Task board
# ---------------------------------------------------------------------------

def new_board(name: str = "Untitled Board") -> dict:
    return {
        "id": _uid(),
        "name": name,
        "tasks": {},       # id -> task dict
        "created_at": _now(),
        "updated_at": _now(),
    }


def new_task(
    title: str,
    parent_id: Optional[str] = None,
    description: str = "",
    prompt: str = "",
    depends_on: Optional[list[str]] = None,
    input_artifacts: Optional[list[str]] = None,
    output_artifact: str = "",
    tool_id: str = "",
    model: str = "GPT-4o",
) -> dict:
    return {
        "id": _uid(),
        "title": title,
        "description": description,
        "prompt": prompt,
        "status": "To Do",
        "parent_id": parent_id,
        "depends_on": depends_on or [],
        "input_artifacts": input_artifacts or [],
        "output_artifact": output_artifact,
        "output_content": "",
        "tool_id": tool_id,
        "model": model,
        "created_at": _now(),
        "updated_at": _now(),
    }


# ---------------------------------------------------------------------------
# Board operations
# ---------------------------------------------------------------------------

def add_task(board: dict, task: dict) -> str:
    board["tasks"][task["id"]] = task
    board["updated_at"] = _now()
    return task["id"]


def delete_task(board: dict, task_id: str) -> list[str]:
    """Delete task and all its children. Returns deleted ids."""
    deleted = _collect_children(board, task_id)
    for tid in deleted:
        board["tasks"].pop(tid, None)
        # Remove from other tasks' depends_on
        for t in board["tasks"].values():
            if tid in t["depends_on"]:
                t["depends_on"].remove(tid)
    board["updated_at"] = _now()
    return deleted


def _collect_children(board: dict, tid: str) -> list[str]:
    result = [tid]
    for t in board["tasks"].values():
        if t["parent_id"] == tid:
            result.extend(_collect_children(board, t["id"]))
    return result


def get_root_tasks(board: dict) -> list[str]:
    return [tid for tid, t in board["tasks"].items() if not t["parent_id"]]


def get_children(board: dict, parent_id: str) -> list[str]:
    return [tid for tid, t in board["tasks"].items() if t["parent_id"] == parent_id]


def get_blocked_by(board: dict, task_id: str) -> list[str]:
    """Return list of dependency task ids that are not Done."""
    task = board["tasks"].get(task_id)
    if not task:
        return []
    return [
        dep_id for dep_id in task["depends_on"]
        if dep_id in board["tasks"] and board["tasks"][dep_id]["status"] != "Done"
    ]


def get_all_task_titles(board: dict) -> dict[str, str]:
    """Return {id: title} for all tasks."""
    return {tid: t["title"] for tid, t in board["tasks"].items()}


def can_run_task(board: dict, task_id: str) -> bool:
    return len(get_blocked_by(board, task_id)) == 0


# ---------------------------------------------------------------------------
# Mock LLM execution
# ---------------------------------------------------------------------------

def run_task(board: dict, task_id: str, model: Optional[str] = None) -> Optional[str]:
    """Execute a task via mock LLM. Returns output content or None if blocked."""
    task = board["tasks"].get(task_id)
    if not task:
        return None

    blocked = get_blocked_by(board, task_id)
    if blocked:
        return None

    model = model or task.get("model", "GPT-4o")
    tool_name = ""
    for t in TOOLS:
        if t["id"] == task.get("tool_id"):
            tool_name = t["name"]
            break

    task["status"] = "In Progress"
    task["updated_at"] = _now()

    # Build context from input artifacts and dependency outputs
    context_parts = []
    for dep_id in task["depends_on"]:
        dep = board["tasks"].get(dep_id)
        if dep and dep.get("output_content"):
            context_parts.append(f"[From {dep['title']}]: {dep['output_content']}")
    for art in task["input_artifacts"]:
        # Try reading file content
        p = Path(art)
        if p.is_file():
            try:
                content = p.read_text(errors="replace")[:500]
                context_parts.append(f"[File: {p.name}]:\n{content}")
            except Exception:
                context_parts.append(f"[File]: {art}")
        else:
            context_parts.append(f"[Artifact]: {art}")

    context = "\n".join(context_parts) if context_parts else "No additional context."
    prompt = task.get("prompt") or task["title"]

    tool_line = f"\nTool: {tool_name}" if tool_name else ""
    # Mock LLM response
    output = (
        f"**[{model}]** Task: {task['title']}{tool_line}\n\n"
        f"Prompt: *{prompt[:200]}*\n\n"
        f"Context: {context[:500]}\n\n"
        f"Generated output for '{task['title']}':\n"
        f"- Analysis point 1\n"
        f"- Analysis point 2\n"
        f"- Recommendation\n"
    )

    task["output_content"] = output
    task["status"] = "Done"
    task["updated_at"] = _now()
    board["updated_at"] = _now()
    return output


def run_all_tasks(board: dict, model: str = "GPT-4o") -> int:
    """Run all runnable tasks in dependency order. Returns count of tasks run."""
    count = 0
    changed = True
    while changed:
        changed = False
        for tid, task in board["tasks"].items():
            if task["status"] == "Done":
                continue
            if can_run_task(board, tid):
                run_task(board, tid, model)
                count += 1
                changed = True
    return count


def reset_board(board: dict) -> None:
    for task in board["tasks"].values():
        task["status"] = "To Do"
        task["output_content"] = ""
    board["updated_at"] = _now()


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------
BOARDS_DIR = Path(__file__).parent / "workspace" / "boards"
BOARDS_DIR.mkdir(parents=True, exist_ok=True)


def save_board(board: dict) -> Path:
    path = BOARDS_DIR / f"{board['id']}.json"
    path.write_text(json.dumps(board, indent=2, ensure_ascii=False))
    return path


def load_board(board_id: str) -> Optional[dict]:
    path = BOARDS_DIR / f"{board_id}.json"
    if path.exists():
        return json.loads(path.read_text())
    return None


def list_boards() -> list[dict]:
    results = []
    for p in sorted(BOARDS_DIR.glob("*.json")):
        try:
            data = json.loads(p.read_text())
            total = len(data["tasks"])
            done = sum(1 for t in data["tasks"].values() if t["status"] == "Done")
            results.append({
                "id": data["id"],
                "name": data["name"],
                "total": total,
                "done": done,
            })
        except Exception:
            continue
    return results


def delete_board_file(board_id: str) -> None:
    path = BOARDS_DIR / f"{board_id}.json"
    if path.exists():
        path.unlink()


# ---------------------------------------------------------------------------
# App domains
# ---------------------------------------------------------------------------
APP_DOMAINS = [
    {
        "id": "management", "name": "Management", "icon": "📊",
        "prompts": ["Create project plan", "Risk assessment", "Status report"],
        "tools": ["llm_generator", "summarizer", "risk_extractor"],
    },
    {
        "id": "hr", "name": "HR", "icon": "👥",
        "prompts": ["Write job description", "Interview questions", "Onboarding checklist"],
        "tools": ["llm_generator", "formatter"],
    },
    {
        "id": "marketing", "name": "Marketing", "icon": "📣",
        "prompts": ["Content plan", "Campaign brief", "Competitor analysis"],
        "tools": ["llm_generator", "summarizer", "classifier"],
    },
    {
        "id": "smm", "name": "SMM", "icon": "📱",
        "prompts": ["Social media post", "Content calendar", "Engagement report"],
        "tools": ["llm_generator", "formatter"],
    },
    {
        "id": "sales", "name": "Sales", "icon": "💰",
        "prompts": ["Sales pitch", "Proposal draft", "Lead qualification"],
        "tools": ["llm_generator", "formatter", "summarizer"],
    },
    {
        "id": "support", "name": "Support", "icon": "🎧",
        "prompts": ["FAQ draft", "Response template", "Ticket analysis"],
        "tools": ["llm_generator", "classifier", "summarizer"],
    },
    {
        "id": "analysis", "name": "Analysis", "icon": "📈",
        "prompts": ["Data summary", "Trend analysis", "Report generation"],
        "tools": ["summarizer", "risk_extractor", "classifier"],
    },
    {
        "id": "design", "name": "Design", "icon": "🎨",
        "prompts": ["Design brief", "UI review", "Style guide"],
        "tools": ["llm_generator", "formatter"],
    },
    {
        "id": "development", "name": "Development", "icon": "💻",
        "prompts": ["Code review", "Architecture doc", "API specification"],
        "tools": ["code_generator", "validator", "formatter"],
    },
    {
        "id": "engineering", "name": "Engineering", "icon": "⚙️",
        "prompts": ["System design", "Infrastructure plan", "Performance report"],
        "tools": ["code_generator", "validator", "summarizer"],
    },
]


# ---------------------------------------------------------------------------
# Branch / Continue / Rerun
# ---------------------------------------------------------------------------

def branch_task(board: dict, task_id: str) -> Optional[dict]:
    """Create a branch (copy) of a task with a new ID."""
    original = board["tasks"].get(task_id)
    if not original:
        return None
    task = new_task(
        title=f"{original['title']} (branch)",
        parent_id=original.get("parent_id"),
        description=original.get("description", ""),
        prompt=original.get("prompt", ""),
        depends_on=list(original.get("depends_on", [])),
        input_artifacts=list(original.get("input_artifacts", [])),
        output_artifact=original.get("output_artifact", ""),
        tool_id=original.get("tool_id", ""),
        model=original.get("model", "GPT-4o"),
    )
    task["branched_from"] = task_id
    add_task(board, task)
    return task


def continue_task(board: dict, task_id: str) -> Optional[dict]:
    """Create a continuation task that depends on the original."""
    original = board["tasks"].get(task_id)
    if not original:
        return None
    task = new_task(
        title=f"{original['title']} (continued)",
        parent_id=original.get("parent_id"),
        depends_on=[task_id],
        model=original.get("model", "GPT-4o"),
    )
    task["continued_from"] = task_id
    add_task(board, task)
    return task


def rerun_task(board: dict, task_id: str) -> Optional[str]:
    """Reset and re-execute a task."""
    task = board["tasks"].get(task_id)
    if not task:
        return None
    task["status"] = "To Do"
    task["output_content"] = ""
    task["updated_at"] = _now()
    return run_task(board, task_id)


def save_output_as_file(board: dict, task_id: str, output_dir: Path) -> Optional[Path]:
    """Save a task's output as a file in the workspace."""
    task = board["tasks"].get(task_id)
    if not task or not task.get("output_content"):
        return None

    filename = task.get("output_artifact") or f"{task['title'].lower().replace(' ', '_')}.md"
    if not any(filename.endswith(ext) for ext in ('.md', '.txt', '.py', '.json', '.csv')):
        filename += ".md"

    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / filename

    content = (
        f"<!-- AI Generated -->\n"
        f"<!-- Source: {task['title']} | Model: {task.get('model', 'unknown')} | "
        f"Task: {task['id']} -->\n\n"
        f"{task['output_content']}"
    )
    path.write_text(content)
    return path
