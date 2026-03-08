"""PlusFlow v0.5 — Flow content with collapsible detail & fullscreen task.

Exports:
  render_flow_content(files_dir)   — board list OR flow+detail
  render_task_fullscreen(files_dir) — single task on full width
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import streamlit as st
from streamlit_agraph import Config, Edge, Node, agraph

from workflow_models import (
    MODELS,
    STATUSES,
    STATUS_ICONS,
    TOOL_NAMES,
    TOOLS,
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
# Node colors
# ---------------------------------------------------------------------------
_NODE_COLORS = {"To Do": "#6c757d", "In Progress": "#f39c12", "Done": "#2ecc71"}
_NODE_FONTS = {"To Do": {"color": "#fff"}, "In Progress": {"color": "#fff"}, "Done": {"color": "#fff"}}


def _get_all_files(base: Path) -> list[Path]:
    files = []
    if not base.exists():
        return files
    for item in sorted(base.iterdir()):
        if item.name.startswith("."):
            continue
        if item.is_dir():
            files.extend(_get_all_files(item))
        else:
            files.append(item)
    return files


# ---------------------------------------------------------------------------
# Board list (no board selected)
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
# Flow view — interactive graph
# ---------------------------------------------------------------------------
def _render_flow_view(board: dict):
    if not board["tasks"]:
        st.info("No tasks yet. Add one below.")
        _render_quick_add(board)
        return

    nodes = []
    edges = []

    for tid, task in board["tasks"].items():
        icon = STATUS_ICONS.get(task["status"], "⬜")
        color = _NODE_COLORS.get(task["status"], "#6c757d")
        font = _NODE_FONTS.get(task["status"], {"color": "#fff"})

        tool_name = ""
        for t in TOOLS:
            if t["id"] == task.get("tool_id"):
                tool_name = t["name"]
                break

        label = f"{icon} {task['title']}"
        if tool_name:
            label += f"\n[{tool_name}]"
        if task.get("output_artifact"):
            art = task["output_artifact"]
            if "/" in art:
                art = Path(art).name
            label += f"\n-> {art}"

        nodes.append(Node(
            id=tid, label=label, color=color, font=font,
            size=25, shape="box",
            borderWidth=3 if st.session_state.get("board_selected_task") == tid else 1,
            borderWidthSelected=4,
            margin={"top": 10, "bottom": 10, "left": 14, "right": 14},
        ))

        if task.get("parent_id") and task["parent_id"] in board["tasks"]:
            edges.append(Edge(source=task["parent_id"], target=tid, color="#555", dashes=True, width=1))

        for dep_id in task.get("depends_on", []):
            if dep_id in board["tasks"]:
                edges.append(Edge(
                    source=dep_id, target=tid, color="#508cff", width=2,
                    arrows={"to": {"enabled": True, "type": "arrow"}},
                ))

    config = Config(
        width="100%", height=500, directed=True, physics=True,
        hierarchical=False, nodeHighlightBehavior=True,
        highlightColor="#508cff", collapsible=False,
    )

    selected = agraph(nodes=nodes, edges=edges, config=config)

    if selected and selected in board["tasks"]:
        if selected != st.session_state.get("board_selected_task"):
            st.session_state["board_selected_task"] = selected
            st.session_state["detail_collapsed"] = False
            st.rerun()

    st.markdown("---")
    _render_quick_add(board)


# ---------------------------------------------------------------------------
# Board view — task list
# ---------------------------------------------------------------------------
def _render_board_view(board: dict):
    roots = get_root_tasks(board)
    if not roots and not st.session_state.get("board_adding_parent"):
        st.session_state["board_adding_parent"] = "__root__"

    for tid in roots:
        _render_task_row(board, tid, depth=0)

    st.markdown("---")
    _render_quick_add(board)


def _render_task_row(board: dict, tid: str, depth: int = 0):
    task = board["tasks"][tid]
    icon = STATUS_ICONS.get(task["status"], "⬜")
    indent = "\u00a0\u00a0\u00a0\u00a0" * depth

    cols = st.columns([4, 1, 1, 1, 0.5])
    with cols[0]:
        if st.button(f"{indent}{icon} {task['title']}", key=f"tsel_{tid}", use_container_width=True):
            st.session_state["board_selected_task"] = tid
            st.session_state["detail_collapsed"] = False
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
# Quick add task form
# ---------------------------------------------------------------------------
def _render_quick_add(board: dict):
    adding = st.session_state.get("board_adding_parent")

    if adding is None:
        if st.button("+ Add task", key="add_root_flow", use_container_width=True):
            st.session_state["board_adding_parent"] = "__root__"
            st.rerun()
        return

    parent_label = "root"
    if adding != "__root__":
        parent = board["tasks"].get(adding)
        parent_label = f"under '{parent['title']}'" if parent else "root"

    st.caption(f"Adding task ({parent_label})")

    with st.form("add_task_form", clear_on_submit=True):
        title = st.text_input("Title", placeholder="e.g. Analyze market")
        prompt = st.text_area("Prompt", placeholder="Task instructions...", height=60)

        fc1, fc2 = st.columns(2)
        with fc1:
            tool_choice = st.selectbox("Tool", TOOL_NAMES, key="new_task_tool")
        with fc2:
            model_choice = st.selectbox("Model", MODELS, key="new_task_model")

        output_art = st.text_input("Output artifact", placeholder="e.g. analysis.md")

        all_titles = get_all_task_titles(board)
        dep_options = {tid: t for tid, t in all_titles.items() if tid != adding}
        dep_selected = st.multiselect("Depends on", options=list(dep_options.keys()),
                                       format_func=lambda x: dep_options.get(x, x))

        bc1, bc2 = st.columns(2)
        with bc1:
            submitted = st.form_submit_button("Add", use_container_width=True)
        with bc2:
            cancelled = st.form_submit_button("Cancel", use_container_width=True)

        if submitted and title.strip():
            tool_id = ""
            if tool_choice != "(no tool)":
                for t in TOOLS:
                    if t["name"] == tool_choice:
                        tool_id = t["id"]
                        break
            parent_id = None if adding == "__root__" else adding
            task = new_task(
                title=title.strip(), parent_id=parent_id, prompt=prompt,
                depends_on=dep_selected, output_artifact=output_art.strip(),
                tool_id=tool_id, model=model_choice,
            )
            add_task(board, task)
            save_board(board)
            st.session_state["board_adding_parent"] = None
            st.rerun()
        if cancelled:
            st.session_state["board_adding_parent"] = None
            st.rerun()


# ---------------------------------------------------------------------------
# Task detail panel (used in both collapsed sidebar and fullscreen)
# ---------------------------------------------------------------------------
def _render_task_detail(board: dict, files_dir: Path, fullscreen: bool = False):
    tid = st.session_state.get("board_selected_task")
    if not tid or tid not in board["tasks"]:
        if not fullscreen:
            st.caption("Click a task to open details.")
        return

    task = board["tasks"][tid]
    icon = STATUS_ICONS.get(task["status"], "⬜")

    # Header with collapse/expand/fullscreen buttons
    if not fullscreen:
        h1, h2, h3 = st.columns([3, 1, 1])
        with h1:
            st.markdown(f"### {icon} {task['title']}")
        with h2:
            if st.button("⤢", key="task_fullscreen_btn", help="Open fullscreen"):
                st.session_state["current_view"] = "task_fullscreen"
                st.rerun()
        with h3:
            if st.button("✕", key="task_close_btn", help="Close panel"):
                st.session_state["board_selected_task"] = None
                st.rerun()
    else:
        h1, h2 = st.columns([5, 1])
        with h1:
            st.markdown(f"## {icon} {task['title']}")
        with h2:
            if st.button("← Back to Flow", key="task_fs_back", use_container_width=True):
                st.session_state["current_view"] = "flow"
                st.rerun()

    # Status
    current_idx = STATUSES.index(task["status"]) if task["status"] in STATUSES else 0
    new_status = st.radio("Status", STATUSES, index=current_idx, key=f"d_st_{tid}", horizontal=True)

    # Title
    new_title = st.text_input("Title", value=task["title"], key=f"d_ti_{tid}")

    # Prompt
    prompt_height = 200 if fullscreen else 100
    new_prompt = st.text_area("Prompt", value=task.get("prompt", ""), key=f"d_pr_{tid}", height=prompt_height)

    # Tool & Model side by side
    tc1, tc2 = st.columns(2)
    with tc1:
        current_tool = "(no tool)"
        for t in TOOLS:
            if t["id"] == task.get("tool_id"):
                current_tool = t["name"]
                break
        tool_idx = TOOL_NAMES.index(current_tool) if current_tool in TOOL_NAMES else 0
        new_tool = st.selectbox("Tool", TOOL_NAMES, index=tool_idx, key=f"d_to_{tid}")
    with tc2:
        current_model = task.get("model", "GPT-4o")
        model_idx = MODELS.index(current_model) if current_model in MODELS else 0
        new_model = st.selectbox("Model", MODELS, index=model_idx, key=f"d_mo_{tid}")

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
    st.markdown("**Input artifacts**")
    current_inputs = list(task.get("input_artifacts", []))
    updated_inputs = list(current_inputs)

    if current_inputs:
        for i, art_path in enumerate(current_inputs):
            ac1, ac2 = st.columns([4, 1])
            with ac1:
                display = Path(art_path).name if "/" in art_path else art_path
                st.caption(f"📎 {display}")
            with ac2:
                if st.button("✕", key=f"d_rmart_{tid}_{i}"):
                    updated_inputs.remove(art_path)
                    task["input_artifacts"] = updated_inputs
                    save_board(board)
                    st.rerun()
    else:
        st.caption("No files attached. Use file tree to select.")

    # Attach file dropdown
    all_files = _get_all_files(files_dir)
    file_options = {str(f): f.name for f in all_files if str(f) not in current_inputs}
    if file_options:
        add_file = st.selectbox(
            "Attach file", options=[""] + list(file_options.keys()),
            format_func=lambda x: file_options.get(x, "Select file..."),
            key=f"d_addfile_{tid}",
        )
        if add_file and st.button("+ Attach", key=f"d_attach_{tid}"):
            if add_file not in task["input_artifacts"]:
                task["input_artifacts"].append(add_file)
                save_board(board)
                st.rerun()

    st.divider()

    # Save
    if st.button("💾 Save", key=f"d_sv_{tid}", use_container_width=True):
        task["title"] = new_title
        task["prompt"] = new_prompt
        task["status"] = new_status
        task["output_artifact"] = new_artifact
        task["parent_id"] = None if new_parent == "__none__" else new_parent
        task["depends_on"] = new_deps
        task["input_artifacts"] = updated_inputs
        task["model"] = new_model
        tool_id = ""
        if new_tool != "(no tool)":
            for t in TOOLS:
                if t["name"] == new_tool:
                    tool_id = t["id"]
                    break
        task["tool_id"] = tool_id
        task["updated_at"] = datetime.now().isoformat(timespec="seconds")
        save_board(board)
        st.rerun()

    # Blocked
    blocked = get_blocked_by(board, tid)
    if blocked:
        names = [board["tasks"][b]["title"] for b in blocked if b in board["tasks"]]
        st.warning(f"Blocked by: {', '.join(names)}")

    # Actions
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
        if st.button("✅ Done", key=f"d_dn_{tid}", use_container_width=True):
            task["status"] = "Done"
            save_board(board)
            st.rerun()
    with btn3:
        if st.button("🗑 Delete", key=f"d_dl_{tid}", use_container_width=True):
            delete_task(board, tid)
            st.session_state["board_selected_task"] = None
            if fullscreen:
                st.session_state["current_view"] = "flow"
            save_board(board)
            st.rerun()

    # Output
    st.divider()
    st.markdown("**Output**")
    if task.get("output_content"):
        st.markdown(task["output_content"])
    else:
        st.caption("No output yet.")


# ---------------------------------------------------------------------------
# EXPORTED: render_flow_content — board list or flow graph + detail
# ---------------------------------------------------------------------------
def render_flow_content(files_dir: Path):
    board = st.session_state.get("board")
    if board is None:
        _render_board_list()
        return

    # Toolbar
    tb = st.columns([0.4, 2, 1, 1, 1, 1])
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
            st.toast("Saved!")

    st.divider()

    # Determine if detail panel is collapsed
    has_selected = (st.session_state.get("board_selected_task")
                    and st.session_state["board_selected_task"] in board["tasks"])
    collapsed = st.session_state.get("detail_collapsed", False)

    if has_selected and not collapsed:
        # Two columns: flow + detail
        main_col, detail_col = st.columns([3, 2])
    else:
        # Full width for flow
        main_col = st.container()
        detail_col = None

    with main_col:
        view = st.session_state.get("board_view", "flow")
        if view == "flow":
            _render_flow_view(board)
        else:
            _render_board_view(board)

    if detail_col is not None:
        with detail_col:
            _render_task_detail(board, files_dir, fullscreen=False)

    # Show expand button when collapsed but task is selected
    if has_selected and collapsed:
        tid = st.session_state["board_selected_task"]
        task = board["tasks"][tid]
        if st.button(f"📋 {task['title']} — click to expand", key="expand_detail", use_container_width=True):
            st.session_state["detail_collapsed"] = False
            st.rerun()


# ---------------------------------------------------------------------------
# EXPORTED: render_task_fullscreen — task detail takes full main area
# ---------------------------------------------------------------------------
def render_task_fullscreen(files_dir: Path):
    board = st.session_state.get("board")
    if board is None:
        st.session_state["current_view"] = "flow"
        st.rerun()
        return

    _render_task_detail(board, files_dir, fullscreen=True)
