"""PlusFlow v0.3 — Task Board + interactive Flow graph."""

from __future__ import annotations

from datetime import datetime

import streamlit as st
from streamlit_agraph import Config, Edge, Node, agraph

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
    "board_view": "flow",  # "board" or "flow" — flow is default now
    "board_adding_parent": None,
}
for k, v in _DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ---------------------------------------------------------------------------
# Color / style helpers
# ---------------------------------------------------------------------------
_NODE_COLORS = {
    "To Do": "#6c757d",
    "In Progress": "#f39c12",
    "Done": "#2ecc71",
}

_NODE_FONTS = {
    "To Do": {"color": "#fff"},
    "In Progress": {"color": "#fff"},
    "Done": {"color": "#fff"},
}


# ---------------------------------------------------------------------------
# Board list (when no board is open)
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
        c1, c2 = st.columns([5, 0.5])
        with c1:
            progress = f"{b['done']}/{b['total']}" if b["total"] else "empty"
            if st.button(f"{b['name']}  ({progress})", key=f"bopen_{b['id']}", use_container_width=True):
                loaded = load_board(b["id"])
                if loaded:
                    st.session_state["board"] = loaded
                    st.session_state["board_selected_task"] = None
                    st.rerun()
        with c2:
            if st.button("🗑", key=f"bdel_{b['id']}"):
                delete_board_file(b["id"])
                st.rerun()


# ---------------------------------------------------------------------------
# Flow view — interactive agraph
# ---------------------------------------------------------------------------
def _render_flow_view(board: dict):
    if not board["tasks"]:
        st.info("No tasks yet. Switch to Board View to add tasks.")
        return

    nodes = []
    edges = []

    for tid, task in board["tasks"].items():
        icon = STATUS_ICONS.get(task["status"], "⬜")
        color = _NODE_COLORS.get(task["status"], "#6c757d")
        font = _NODE_FONTS.get(task["status"], {"color": "#fff"})

        label = f"{icon} {task['title']}"
        if task.get("output_artifact"):
            label += f"\n[{task['output_artifact']}]"

        nodes.append(Node(
            id=tid,
            label=label,
            color=color,
            font=font,
            size=25,
            shape="box",
            borderWidth=3 if st.session_state.get("board_selected_task") == tid else 1,
            borderWidthSelected=4,
            margin={"top": 10, "bottom": 10, "left": 14, "right": 14},
        ))

        # Parent-child edges (hierarchy) — dashed gray
        if task.get("parent_id") and task["parent_id"] in board["tasks"]:
            edges.append(Edge(
                source=task["parent_id"],
                target=tid,
                color="#555",
                dashes=True,
                width=1,
                label="child",
                font={"size": 9, "color": "#777"},
            ))

        # Dependency edges — solid blue
        for dep_id in task.get("depends_on", []):
            if dep_id in board["tasks"]:
                edges.append(Edge(
                    source=dep_id,
                    target=tid,
                    color="#508cff",
                    width=2,
                    label="depends",
                    font={"size": 9, "color": "#508cff"},
                    arrows={"to": {"enabled": True, "type": "arrow"}},
                ))

    config = Config(
        width="100%",
        height=500,
        directed=True,
        physics=True,
        hierarchical=False,
        nodeHighlightBehavior=True,
        highlightColor="#508cff",
        collapsible=False,
        node={"renderLabel": True},
        link={"renderLabel": True},
    )

    selected = agraph(nodes=nodes, edges=edges, config=config)

    # If user clicked a node in the graph, select it
    if selected and selected in board["tasks"]:
        if selected != st.session_state.get("board_selected_task"):
            st.session_state["board_selected_task"] = selected
            st.rerun()


# ---------------------------------------------------------------------------
# Board view — hierarchical card list for adding/managing tasks
# ---------------------------------------------------------------------------
def _render_board_view(board: dict):
    roots = get_root_tasks(board)

    if not roots and not st.session_state.get("board_adding_parent"):
        st.session_state["board_adding_parent"] = "__root__"

    for tid in roots:
        _render_task_row(board, tid, depth=0)

    st.markdown("---")
    _render_add_task_form(board)


def _render_task_row(board: dict, tid: str, depth: int = 0):
    task = board["tasks"][tid]
    icon = STATUS_ICONS.get(task["status"], "⬜")
    indent = "—" * depth + " " if depth > 0 else ""
    is_selected = st.session_state.get("board_selected_task") == tid

    label = f"{indent}{icon} **{task['title']}**"
    if task.get("output_artifact"):
        label += f"  `{task['output_artifact']}`"

    blocked = get_blocked_by(board, tid)

    cols = st.columns([4, 1, 1, 1, 0.5])
    with cols[0]:
        if st.button(
            f"{indent}{icon} {task['title']}",
            key=f"tsel_{tid}",
            use_container_width=True,
        ):
            st.session_state["board_selected_task"] = tid
            st.rerun()
    with cols[1]:
        st.caption(task["status"])
    with cols[2]:
        if task["status"] != "Done" and can_run_task(board, tid):
            if st.button("▶", key=f"trun_{tid}"):
                run_task(board, tid)
                save_board(board)
                st.session_state["board_selected_task"] = tid
                st.rerun()
        elif blocked:
            st.caption("blocked")
    with cols[3]:
        if st.button("+ sub", key=f"tsub_{tid}"):
            st.session_state["board_adding_parent"] = tid
            st.rerun()
    with cols[4]:
        if st.button("🗑", key=f"tdel_{tid}"):
            delete_task(board, tid)
            if st.session_state.get("board_selected_task") == tid:
                st.session_state["board_selected_task"] = None
            save_board(board)
            st.rerun()

    for cid in get_children(board, tid):
        _render_task_row(board, cid, depth + 1)


# ---------------------------------------------------------------------------
# Add task form
# ---------------------------------------------------------------------------
def _render_add_task_form(board: dict):
    adding = st.session_state.get("board_adding_parent")

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
        prompt = st.text_area("Prompt", placeholder="What should this task do?", height=80)
        output_art = st.text_input("Output artifact", placeholder="e.g. market_analysis.md")

        all_titles = get_all_task_titles(board)
        dep_options = {tid: t for tid, t in all_titles.items() if tid != adding}
        dep_selected = st.multiselect(
            "Depends on",
            options=list(dep_options.keys()),
            format_func=lambda x: dep_options.get(x, x),
        )

        c1, c2 = st.columns(2)
        with c1:
            submitted = st.form_submit_button("Add", use_container_width=True)
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
# Task detail panel (right side)
# ---------------------------------------------------------------------------
def _render_task_detail(board: dict):
    tid = st.session_state.get("board_selected_task")
    if not tid or tid not in board["tasks"]:
        st.caption("Click a node in the graph or a task in the list to open it.")
        return

    task = board["tasks"][tid]
    icon = STATUS_ICONS.get(task["status"], "⬜")

    st.markdown(f"### {icon} {task['title']}")

    # Status radio
    current_idx = STATUSES.index(task["status"]) if task["status"] in STATUSES else 0
    new_status = st.radio("Status", STATUSES, index=current_idx, key=f"d_st_{tid}", horizontal=True)

    # Title
    new_title = st.text_input("Title", value=task["title"], key=f"d_ti_{tid}")

    # Prompt
    new_prompt = st.text_area("Prompt", value=task.get("prompt", ""), key=f"d_pr_{tid}", height=100)

    # Output artifact
    new_artifact = st.text_input("Output artifact", value=task.get("output_artifact", ""), key=f"d_ar_{tid}")

    # Parent
    all_titles = get_all_task_titles(board)
    parent_opts = {"__none__": "(no parent)"}
    for t_id, t_title in all_titles.items():
        if t_id != tid:
            parent_opts[t_id] = t_title
    cur_parent = task.get("parent_id") or "__none__"
    if cur_parent not in parent_opts:
        cur_parent = "__none__"
    pkeys = list(parent_opts.keys())
    new_parent = st.selectbox("Parent", pkeys, index=pkeys.index(cur_parent),
                               format_func=lambda x: parent_opts[x], key=f"d_pa_{tid}")

    # Dependencies
    dep_opts = {t_id: t_title for t_id, t_title in all_titles.items() if t_id != tid}
    cur_deps = [d for d in task.get("depends_on", []) if d in dep_opts]
    new_deps = st.multiselect("Depends on", options=list(dep_opts.keys()), default=cur_deps,
                               format_func=lambda x: dep_opts.get(x, x), key=f"d_de_{tid}")

    # Input artifacts
    input_arts = st.text_input("Input artifacts (comma-separated)",
                                value=", ".join(task.get("input_artifacts", [])), key=f"d_in_{tid}")

    # Save
    if st.button("Save", key=f"d_sv_{tid}", use_container_width=True):
        task["title"] = new_title
        task["prompt"] = new_prompt
        task["status"] = new_status
        task["output_artifact"] = new_artifact
        task["parent_id"] = None if new_parent == "__none__" else new_parent
        task["depends_on"] = new_deps
        task["input_artifacts"] = [a.strip() for a in input_arts.split(",") if a.strip()]
        task["updated_at"] = datetime.now().isoformat(timespec="seconds")
        save_board(board)
        st.rerun()

    st.divider()

    # Blocked info
    blocked = get_blocked_by(board, tid)
    if blocked:
        names = [board["tasks"][b]["title"] for b in blocked if b in board["tasks"]]
        st.warning(f"Blocked by: {', '.join(names)}")

    # Action buttons
    btn1, btn2, btn3 = st.columns(3)
    with btn1:
        if task["status"] != "Done":
            if can_run_task(board, tid):
                if st.button("▶ Run", key=f"d_ru_{tid}", use_container_width=True):
                    run_task(board, tid)
                    save_board(board)
                    st.rerun()
            else:
                st.button("▶ Run", key=f"d_ru_{tid}", use_container_width=True, disabled=True)
    with btn2:
        if st.button("Done", key=f"d_dn_{tid}", use_container_width=True):
            task["status"] = "Done"
            save_board(board)
            st.rerun()
    with btn3:
        if st.button("🗑 Delete", key=f"d_dl_{tid}", use_container_width=True):
            delete_task(board, tid)
            st.session_state["board_selected_task"] = None
            save_board(board)
            st.rerun()

    # Output
    st.divider()
    st.markdown("**Output**")
    if task.get("output_content"):
        st.markdown(task["output_content"])
    else:
        st.caption("No output yet. Run the task to generate.")


# ---------------------------------------------------------------------------
# Main render
# ---------------------------------------------------------------------------
def render_flow_page():
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
        view = st.session_state.get("board_view", "flow")
        if view == "flow":
            if st.button("Board View", key="to_board", use_container_width=True):
                st.session_state["board_view"] = "board"
                st.rerun()
        else:
            if st.button("Flow View", key="to_flow", use_container_width=True):
                st.session_state["board_view"] = "flow"
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

    # Layout: graph/board + detail panel
    view = st.session_state.get("board_view", "flow")
    main_col, detail_col = st.columns([3, 1.5])

    with main_col:
        if view == "flow":
            _render_flow_view(board)
        else:
            _render_board_view(board)

    with detail_col:
        _render_task_detail(board)
