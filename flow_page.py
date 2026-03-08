"""PlusFlow v0.2 — Task Board + Flow View page."""

from __future__ import annotations

import streamlit as st

from workflow_models import (
    STATUSES,
    STATUS_ICONS,
    add_task,
    can_run_task,
    delete_board_file,
    delete_task,
    get_all_task_titles,
    get_blocked_by,
    get_children,
    get_root_tasks,
    list_boards,
    load_board,
    new_board,
    new_task,
    reset_board,
    run_all_tasks,
    run_task,
    save_board,
)


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
_DEFAULTS = {
    "board": None,
    "board_selected_task": None,
    "board_view": "board",  # "board" or "flow"
    "board_adding_parent": None,  # parent_id or "__root__"
}
for k, v in _DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ---------------------------------------------------------------------------
# CSS for task cards
# ---------------------------------------------------------------------------
def _inject_css():
    st.markdown("""
    <style>
    .task-card {
        border: 1px solid #444;
        border-radius: 8px;
        padding: 10px 14px;
        margin: 4px 0;
        cursor: pointer;
    }
    .task-card:hover { border-color: #508cff; }
    .task-card-selected { border: 2px solid #508cff; background: rgba(80,140,255,0.08); }
    .task-card-todo { border-left: 4px solid #888; }
    .task-card-inprogress { border-left: 4px solid #f39c12; }
    .task-card-done { border-left: 4px solid #2ecc71; }
    .task-card .task-title { font-weight: 600; font-size: 0.95rem; }
    .task-card .task-meta { font-size: 0.8rem; color: #999; margin-top: 2px; }
    .indent-1 { margin-left: 24px; }
    .indent-2 { margin-left: 48px; }
    .indent-3 { margin-left: 72px; }
    </style>
    """, unsafe_allow_html=True)


def _status_css(status: str) -> str:
    return {
        "To Do": "task-card-todo",
        "In Progress": "task-card-inprogress",
        "Done": "task-card-done",
    }.get(status, "")


# ---------------------------------------------------------------------------
# Board list page
# ---------------------------------------------------------------------------
def _render_board_list():
    st.markdown("### Task Boards")

    col1, col2 = st.columns([3, 1])
    with col1:
        name = st.text_input("Board name", placeholder="Product Research", label_visibility="collapsed")
    with col2:
        if st.button("+ New Board", use_container_width=True):
            b = new_board(name.strip() if name else "Untitled Board")
            save_board(b)
            st.session_state["board"] = b
            st.rerun()

    st.divider()

    boards = list_boards()
    if not boards:
        st.info("No boards yet. Create one above.")
        return

    for b in boards:
        c1, c2, c3 = st.columns([4, 1, 0.5])
        with c1:
            progress = f"{b['done']}/{b['total']}" if b["total"] else "empty"
            if st.button(f"{b['name']}  ({progress})", key=f"bopen_{b['id']}", use_container_width=True):
                loaded = load_board(b["id"])
                if loaded:
                    st.session_state["board"] = loaded
                    st.session_state["board_selected_task"] = None
                    st.rerun()
        with c2:
            st.caption(f"{b['done']}/{b['total']}")
        with c3:
            if st.button("🗑", key=f"bdel_{b['id']}"):
                delete_board_file(b["id"])
                st.rerun()


# ---------------------------------------------------------------------------
# Render task card (HTML)
# ---------------------------------------------------------------------------
def _render_task_card_html(board: dict, tid: str, depth: int = 0):
    """Render a task card as HTML + action buttons, then recurse for children."""
    task = board["tasks"][tid]
    is_selected = st.session_state["board_selected_task"] == tid
    status = task["status"]
    icon = STATUS_ICONS.get(status, "⬜")

    selected_cls = "task-card-selected" if is_selected else ""
    status_cls = _status_css(status)
    indent_cls = f"indent-{min(depth, 3)}" if depth > 0 else ""

    # Dependencies info
    dep_names = []
    for dep_id in task.get("depends_on", []):
        dep = board["tasks"].get(dep_id)
        if dep:
            dep_names.append(dep["title"])
    dep_text = f"Depends on: {', '.join(dep_names)}" if dep_names else ""

    # Blocked?
    blocked = get_blocked_by(board, tid)
    blocked_text = ""
    if blocked:
        blocked_names = [board["tasks"][b]["title"] for b in blocked if b in board["tasks"]]
        blocked_text = f"<span style='color:#e74c3c;font-size:0.8rem;'>Blocked by: {', '.join(blocked_names)}</span>"

    # Artifact info
    art_text = ""
    if task.get("output_artifact"):
        art_text = f"Artifact: {task['output_artifact']}"

    st.markdown(
        f"""<div class="task-card {status_cls} {selected_cls} {indent_cls}">
            <div class="task-title">{icon} {task['title']}</div>
            <div class="task-meta">
                {dep_text}
                {'&nbsp;&nbsp;' if dep_text and art_text else ''}{art_text}
            </div>
            {blocked_text}
        </div>""",
        unsafe_allow_html=True,
    )

    # Action buttons
    cols = st.columns([1, 1, 1, 1])
    with cols[0]:
        if st.button("Open", key=f"topen_{tid}", use_container_width=True):
            st.session_state["board_selected_task"] = tid
            st.rerun()
    with cols[1]:
        if status != "Done":
            if can_run_task(board, tid):
                if st.button("Run", key=f"trun_{tid}", use_container_width=True):
                    run_task(board, tid)
                    save_board(board)
                    st.session_state["board_selected_task"] = tid
                    st.rerun()
            else:
                st.button("Run", key=f"trun_{tid}", use_container_width=True, disabled=True)
    with cols[2]:
        if st.button("+ Sub", key=f"tsub_{tid}", use_container_width=True):
            st.session_state["board_adding_parent"] = tid
            st.rerun()
    with cols[3]:
        if st.button("🗑", key=f"tdel_{tid}", use_container_width=True):
            delete_task(board, tid)
            if st.session_state["board_selected_task"] == tid:
                st.session_state["board_selected_task"] = None
            save_board(board)
            st.rerun()

    # Recurse children
    children = get_children(board, tid)
    for cid in children:
        _render_task_card_html(board, cid, depth + 1)


# ---------------------------------------------------------------------------
# Board view
# ---------------------------------------------------------------------------
def _render_board_view(board: dict):
    roots = get_root_tasks(board)

    if not roots and not st.session_state.get("board_adding_parent"):
        st.info("No tasks yet. Add a root task below.")
        st.session_state["board_adding_parent"] = "__root__"

    for tid in roots:
        _render_task_card_html(board, tid, depth=0)

    # Add task form
    _render_add_task_form(board)


# ---------------------------------------------------------------------------
# Add task form
# ---------------------------------------------------------------------------
def _render_add_task_form(board: dict):
    adding = st.session_state.get("board_adding_parent")

    # Always show "Add root task" button
    if adding is None:
        if st.button("+ Add root task", key="add_root", use_container_width=True):
            st.session_state["board_adding_parent"] = "__root__"
            st.rerun()
        return

    parent_label = "root level"
    if adding != "__root__":
        parent = board["tasks"].get(adding)
        parent_label = f"under '{parent['title']}'" if parent else "root level"

    st.markdown(f"**Add task** ({parent_label})")

    with st.form("add_task_form", clear_on_submit=True):
        title = st.text_input("Title", placeholder="e.g. Analyze market")
        prompt = st.text_area("Prompt / description", placeholder="What should this task do?", height=80)
        output_art = st.text_input("Output artifact name", placeholder="e.g. market_analysis.md")

        # Dependencies
        all_titles = get_all_task_titles(board)
        dep_options = {tid: t for tid, t in all_titles.items() if tid != adding}
        dep_selected = st.multiselect("Depends on", options=list(dep_options.keys()),
                                       format_func=lambda x: dep_options.get(x, x))

        c1, c2 = st.columns(2)
        with c1:
            submitted = st.form_submit_button("Add task", use_container_width=True)
        with c2:
            cancelled = st.form_submit_button("Cancel", use_container_width=True)

        if submitted and title.strip():
            parent_id = None if adding == "__root__" else adding
            task = new_task(
                title=title.strip(),
                parent_id=parent_id,
                prompt=prompt,
                depends_on=dep_selected,
                output_artifact=output_art.strip(),
            )
            add_task(board, task)
            save_board(board)
            st.session_state["board_adding_parent"] = None
            st.rerun()

        if cancelled:
            st.session_state["board_adding_parent"] = None
            st.rerun()


# ---------------------------------------------------------------------------
# Flow view (read-only graph overview)
# ---------------------------------------------------------------------------
def _render_flow_view(board: dict):
    if not board["tasks"]:
        st.info("No tasks to visualize.")
        return

    st.markdown("#### Dependency & hierarchy graph")

    # Build a text-based graph visualization
    lines = []
    roots = get_root_tasks(board)

    def _render_tree(tid: str, prefix: str = "", is_last: bool = True):
        task = board["tasks"][tid]
        icon = STATUS_ICONS.get(task["status"], "⬜")
        connector = "└─ " if is_last else "├─ "
        dep_info = ""
        if task["depends_on"]:
            dep_names = [board["tasks"][d]["title"] for d in task["depends_on"] if d in board["tasks"]]
            if dep_names:
                dep_info = f"  ← [{', '.join(dep_names)}]"
        lines.append(f"{prefix}{connector}{icon} **{task['title']}**{dep_info}")
        children = get_children(board, tid)
        for i, cid in enumerate(children):
            child_prefix = prefix + ("   " if is_last else "│  ")
            _render_tree(cid, child_prefix, i == len(children) - 1)

    for i, rid in enumerate(roots):
        task = board["tasks"][rid]
        icon = STATUS_ICONS.get(task["status"], "⬜")
        dep_info = ""
        if task["depends_on"]:
            dep_names = [board["tasks"][d]["title"] for d in task["depends_on"] if d in board["tasks"]]
            if dep_names:
                dep_info = f"  ← [{', '.join(dep_names)}]"
        lines.append(f"{icon} **{task['title']}**{dep_info}")
        children = get_children(board, rid)
        for j, cid in enumerate(children):
            _render_tree(cid, "  ", j == len(children) - 1)
        if i < len(roots) - 1:
            lines.append("")

    st.markdown("\n\n".join(lines))

    # Dependency arrows summary
    st.divider()
    st.markdown("#### Dependency links")
    has_deps = False
    for tid, task in board["tasks"].items():
        if task["depends_on"]:
            for dep_id in task["depends_on"]:
                dep = board["tasks"].get(dep_id)
                if dep:
                    has_deps = True
                    dep_status = STATUS_ICONS.get(dep["status"], "⬜")
                    task_status = STATUS_ICONS.get(task["status"], "⬜")
                    st.markdown(f"{dep_status} {dep['title']}  **→**  {task_status} {task['title']}")
    if not has_deps:
        st.caption("No dependencies defined between tasks.")


# ---------------------------------------------------------------------------
# Task detail panel
# ---------------------------------------------------------------------------
def _render_task_detail(board: dict):
    tid = st.session_state.get("board_selected_task")
    if not tid or tid not in board["tasks"]:
        st.caption("Select a task to see details.")
        return

    task = board["tasks"][tid]
    icon = STATUS_ICONS.get(task["status"], "⬜")

    st.markdown(f"#### {icon} {task['title']}")

    # Status
    current_idx = STATUSES.index(task["status"]) if task["status"] in STATUSES else 0
    new_status = st.radio("Status", STATUSES, index=current_idx, key=f"det_status_{tid}", horizontal=True)

    # Title
    new_title = st.text_input("Title", value=task["title"], key=f"det_title_{tid}")

    # Prompt
    new_prompt = st.text_area("Prompt", value=task.get("prompt", ""), key=f"det_prompt_{tid}", height=100)

    # Output artifact name
    new_artifact = st.text_input("Output artifact", value=task.get("output_artifact", ""), key=f"det_art_{tid}")

    # Parent
    all_titles = get_all_task_titles(board)
    parent_options = {"__none__": "(no parent)"}
    for t_id, t_title in all_titles.items():
        if t_id != tid:
            parent_options[t_id] = t_title
    current_parent = task.get("parent_id") or "__none__"
    if current_parent not in parent_options:
        current_parent = "__none__"
    parent_keys = list(parent_options.keys())
    new_parent = st.selectbox(
        "Parent task",
        parent_keys,
        index=parent_keys.index(current_parent),
        format_func=lambda x: parent_options[x],
        key=f"det_parent_{tid}",
    )

    # Dependencies
    dep_options = {t_id: t_title for t_id, t_title in all_titles.items() if t_id != tid}
    current_deps = [d for d in task.get("depends_on", []) if d in dep_options]
    new_deps = st.multiselect(
        "Depends on",
        options=list(dep_options.keys()),
        default=current_deps,
        format_func=lambda x: dep_options.get(x, x),
        key=f"det_deps_{tid}",
    )

    # Input artifacts (file names)
    input_arts = st.text_input(
        "Input artifacts (comma-separated)",
        value=", ".join(task.get("input_artifacts", [])),
        key=f"det_inputs_{tid}",
    )

    # Save button
    if st.button("Save changes", key=f"det_save_{tid}", use_container_width=True):
        task["title"] = new_title
        task["prompt"] = new_prompt
        task["status"] = new_status
        task["output_artifact"] = new_artifact
        task["parent_id"] = None if new_parent == "__none__" else new_parent
        task["depends_on"] = new_deps
        task["input_artifacts"] = [a.strip() for a in input_arts.split(",") if a.strip()]
        task["updated_at"] = __import__("datetime").datetime.now().isoformat(timespec="seconds")
        save_board(board)
        st.rerun()

    st.divider()

    # Blocked info
    blocked = get_blocked_by(board, tid)
    if blocked:
        blocked_names = [board["tasks"][b]["title"] for b in blocked if b in board["tasks"]]
        st.warning(f"Blocked by: {', '.join(blocked_names)}")

    # Run button
    if task["status"] != "Done":
        if can_run_task(board, tid):
            if st.button("▶ Run task", key=f"det_run_{tid}", use_container_width=True):
                run_task(board, tid)
                save_board(board)
                st.rerun()
        else:
            st.button("▶ Run task", key=f"det_run_{tid}", use_container_width=True, disabled=True)

    if st.button("Mark Done", key=f"det_done_{tid}", use_container_width=True):
        task["status"] = "Done"
        save_board(board)
        st.rerun()

    st.divider()

    # Output
    st.markdown("**Output**")
    if task.get("output_content"):
        st.markdown(task["output_content"])
    else:
        st.caption("No output yet. Run the task to generate output.")


# ---------------------------------------------------------------------------
# Main render
# ---------------------------------------------------------------------------
def render_flow_page():
    _inject_css()

    board = st.session_state.get("board")
    if board is None:
        _render_board_list()
        return

    # Toolbar
    tb = st.columns([0.4, 2.5, 1, 1, 1, 1, 1])
    with tb[0]:
        if st.button("←", key="board_back", use_container_width=True):
            save_board(board)
            st.session_state["board"] = None
            st.session_state["board_selected_task"] = None
            st.session_state["board_adding_parent"] = None
            st.rerun()
    with tb[1]:
        total = len(board["tasks"])
        done = sum(1 for t in board["tasks"].values() if t["status"] == "Done")
        st.markdown(f"### {board['name']}  ({done}/{total})")
    with tb[2]:
        view = st.session_state.get("board_view", "board")
        if view == "board":
            if st.button("Flow View", key="to_flow", use_container_width=True):
                st.session_state["board_view"] = "flow"
                st.rerun()
        else:
            if st.button("Board View", key="to_board", use_container_width=True):
                st.session_state["board_view"] = "board"
                st.rerun()
    with tb[3]:
        if board["tasks"]:
            if st.button("▶ Run All", key="run_all", use_container_width=True):
                run_all_tasks(board)
                save_board(board)
                st.rerun()
    with tb[4]:
        if board["tasks"]:
            if st.button("↺ Reset", key="reset_all", use_container_width=True):
                reset_board(board)
                save_board(board)
                st.rerun()
    with tb[5]:
        if st.button("💾 Save", key="board_save", use_container_width=True):
            save_board(board)
            st.toast("Board saved!")
    with tb[6]:
        new_name = st.text_input("Name", value=board["name"], key="board_rename", label_visibility="collapsed")
        if new_name != board["name"]:
            board["name"] = new_name

    st.divider()

    # Main layout
    view = st.session_state.get("board_view", "board")

    if view == "flow":
        main_col, detail_col = st.columns([3, 1.5])
        with main_col:
            _render_flow_view(board)
        with detail_col:
            st.markdown("#### Task details")
            _render_task_detail(board)
    else:
        main_col, detail_col = st.columns([3, 1.5])
        with main_col:
            _render_board_view(board)
        with detail_col:
            st.markdown("#### Task details")
            _render_task_detail(board)
