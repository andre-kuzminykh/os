"""AI Business OS — v1.0

Layout: Apps bar (top) + Files (left) + Composer & Flow (center) + Inspector (right)
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import streamlit as st
from streamlit_tree_select import tree_select

from flow_page import (
    render_board_list,
    render_board_list_view,
    render_flow_graph,
    render_flow_toolbar,
    render_task_detail,
)
from workflow_models import (
    APP_DOMAINS,
    MODELS,
    TOOL_NAMES,
    TOOLS,
    add_task,
    new_task,
    save_board,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
WORKSPACE = Path(__file__).parent / "workspace"
FILES_DIR = WORKSPACE / "files"
FILES_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Session state defaults
# ---------------------------------------------------------------------------
DEFAULTS = {
    # Layout
    "left_panel_visible": True,
    # Apps
    "active_app": None,              # selected domain id or None
    # Inspector
    "inspector_mode": "none",        # "none" | "task" | "file" | "folder"
    "inspector_file": None,
    "inspector_folder": None,
    # Chat
    "file_messages": [],
    "selected_model": MODELS[0],
    # Flow / Board
    "board": None,
    "board_selected_task": None,
    "board_view": "flow",
    "board_adding_parent": None,
    # Composer
    "composer_prompt": "",
}
for key, val in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = val

# ---------------------------------------------------------------------------
# Mock LLM
# ---------------------------------------------------------------------------
def call_llm(prompt: str, model: str = "GPT-4o", context_files: Optional[list[Path]] = None) -> str:
    ctx = ""
    if context_files:
        names = [f.name for f in context_files]
        ctx = f"\n\nContext files: {', '.join(names)}"
    return (
        f"**[{model}]** Response:{ctx}\n\n"
        f"You asked: *{prompt[:120]}{'…' if len(prompt) > 120 else ''}*\n\n"
        "1. **Point A** — Important observation.\n"
        "2. **Point B** — Consider this.\n"
        "3. **Point C** — Worth exploring.\n\n"
        "Let me know if you'd like to dive deeper."
    )

# ---------------------------------------------------------------------------
# Page config & CSS
# ---------------------------------------------------------------------------
st.set_page_config(page_title="AI Business OS", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    [data-testid="stSidebar"] { display: none; }
    .block-container { padding-top: 0.5rem; padding-bottom: 0; }

    /* Tree select tweaks */
    .rct-checkbox { display: none !important; }
    .rct-node-leaf .rct-title,
    .rct-node-parent .rct-title {
        cursor: pointer !important;
    }
    .rct-node-leaf .rct-title:hover,
    .rct-node-parent .rct-title:hover {
        color: #508cff !important;
    }

    /* Compact headings */
    h1 { font-size: 1.3rem !important; margin-bottom: 0 !important; }
    h3 { font-size: 1rem !important; margin-bottom: 0.3rem !important; }

    /* Apps bar styling */
    .apps-bar {
        display: flex;
        gap: 0;
        border-bottom: 2px solid #333;
        margin-bottom: 0.5rem;
        padding: 0 0.5rem;
        overflow-x: auto;
    }
    .apps-bar .app-tab {
        padding: 0.4rem 0.8rem;
        cursor: pointer;
        border: none;
        background: transparent;
        color: #aaa;
        font-size: 0.85rem;
        white-space: nowrap;
        border-bottom: 2px solid transparent;
        margin-bottom: -2px;
        transition: all 0.15s;
    }
    .apps-bar .app-tab:hover {
        color: #fff;
        background: rgba(255,255,255,0.05);
    }
    .apps-bar .app-tab.active {
        color: #508cff;
        border-bottom-color: #508cff;
    }

    /* Inspector sections */
    .inspector-header {
        font-size: 0.85rem;
        color: #888;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 0.3rem;
    }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Helper: build tree nodes
# ---------------------------------------------------------------------------
def build_tree_nodes(base: Path) -> list[dict]:
    nodes = []
    if not base.exists():
        return nodes
    for item in sorted(base.iterdir()):
        if item.name.startswith("."):
            continue
        if item.is_dir():
            children = build_tree_nodes(item)
            nodes.append({
                "label": f"📁 {item.name}",
                "value": str(item),
                "children": children if children else [],
            })
        else:
            # Mark AI-generated files
            is_ai = False
            try:
                head = item.read_text(errors="replace")[:50]
                if "<!-- AI Generated" in head:
                    is_ai = True
            except Exception:
                pass
            icon = "🤖" if is_ai else "📄"
            nodes.append({
                "label": f"{icon} {item.name}",
                "value": str(item),
            })
    return nodes


def get_files_in_folder(folder: Path) -> list[Path]:
    files = []
    if not folder.exists():
        return files
    for item in sorted(folder.iterdir()):
        if item.name.startswith("."):
            continue
        if item.is_dir():
            files.extend(get_files_in_folder(item))
        else:
            files.append(item)
    return files


# ===========================================================================
# TOP BAR: Apps panel
# ===========================================================================
def render_apps_bar():
    cols = st.columns(len(APP_DOMAINS) + 1)
    active = st.session_state.get("active_app")

    # All apps button
    with cols[0]:
        label = "🏠 All" if active is None else "🏠"
        if st.button(label, key="app_all", use_container_width=True,
                     type="primary" if active is None else "secondary"):
            st.session_state["active_app"] = None
            st.rerun()

    for i, app in enumerate(APP_DOMAINS):
        with cols[i + 1]:
            is_active = active == app["id"]
            btn_label = f"{app['icon']} {app['name']}"
            if st.button(btn_label, key=f"app_{app['id']}", use_container_width=True,
                         type="primary" if is_active else "secondary"):
                st.session_state["active_app"] = app["id"]
                st.rerun()


# ===========================================================================
# LEFT PANEL: Files & Sources
# ===========================================================================
def render_file_tree():
    # Toggle button
    tc1, tc2 = st.columns([3, 1])
    with tc1:
        st.markdown("### 📂 Files")
    with tc2:
        if st.button("◀", key="collapse_left", help="Collapse panel"):
            st.session_state["left_panel_visible"] = False
            st.rerun()

    # New file
    if st.button("＋ New file", key="new_file_btn", use_container_width=True):
        st.session_state["create_new"] = True

    if st.session_state.get("create_new"):
        with st.form("create_form", clear_on_submit=True):
            new_name = st.text_input("File name", placeholder="notes.md")
            c1, c2 = st.columns(2)
            with c1:
                submitted = st.form_submit_button("Create")
            with c2:
                cancelled = st.form_submit_button("Cancel")
            if submitted and new_name:
                if "." not in new_name:
                    new_name += ".md"
                new_path = FILES_DIR / new_name
                new_path.parent.mkdir(parents=True, exist_ok=True)
                new_path.write_text(f"# {new_name.rsplit('.', 1)[0]}\n\n")
                st.session_state["create_new"] = False
                _open_file_inspector(str(new_path))
                st.rerun()
            if cancelled:
                st.session_state["create_new"] = False
                st.rerun()

    # New folder
    if st.button("📁 New folder", key="new_folder_btn", use_container_width=True):
        st.session_state["create_new_folder"] = True

    if st.session_state.get("create_new_folder"):
        with st.form("create_folder_form", clear_on_submit=True):
            folder_name = st.text_input("Folder name", placeholder="research")
            fc1, fc2 = st.columns(2)
            with fc1:
                f_submitted = st.form_submit_button("Create")
            with fc2:
                f_cancelled = st.form_submit_button("Cancel")
            if f_submitted and folder_name:
                (FILES_DIR / folder_name.strip()).mkdir(parents=True, exist_ok=True)
                st.session_state["create_new_folder"] = False
                st.rerun()
            if f_cancelled:
                st.session_state["create_new_folder"] = False
                st.rerun()

    st.divider()

    # Sources section (mocked connectors)
    with st.expander("🔗 Sources", expanded=False):
        st.caption("Git — not connected")
        st.caption("Confluence — not connected")
        st.caption("Google Drive — not connected")
        if st.button("+ Connect source", key="connect_src", use_container_width=True):
            st.toast("Connectors coming soon")

    st.divider()

    # Tree
    nodes = build_tree_nodes(FILES_DIR)
    if not nodes:
        st.caption("No files yet.")
        return

    prev_checked = []
    if st.session_state.get("inspector_file"):
        prev_checked = [st.session_state["inspector_file"]]

    result = tree_select(
        nodes,
        check_model="leaf",
        checked=prev_checked,
        expanded=[str(FILES_DIR)],
        expand_on_click=True,
        only_leaf_checkboxes=True,
        no_cascade=True,
        key="global_tree",
    )

    checked = result.get("checked", [])

    if checked:
        selected_path = checked[-1]
        p = Path(selected_path)
        if p.is_file():
            if selected_path != st.session_state.get("inspector_file"):
                _open_file_inspector(selected_path)
                st.rerun()
        elif p.is_dir():
            if selected_path != st.session_state.get("inspector_folder"):
                _open_folder_inspector(selected_path)
                st.rerun()


def _open_file_inspector(file_path: str):
    """Open file chat in the right inspector."""
    st.session_state["inspector_mode"] = "file"
    st.session_state["inspector_file"] = file_path
    st.session_state["inspector_folder"] = None
    st.session_state["file_messages"] = []


def _open_folder_inspector(folder_path: str):
    """Open folder chat in the right inspector."""
    st.session_state["inspector_mode"] = "folder"
    st.session_state["inspector_folder"] = folder_path
    st.session_state["inspector_file"] = None
    st.session_state["file_messages"] = []


# ===========================================================================
# CENTER: Universal Task Composer + Flow
# ===========================================================================
def render_center():
    board = st.session_state.get("board")

    if board is None:
        # Show composer + board list
        render_composer()
        st.divider()
        render_board_list()
    else:
        # Toolbar + composer + flow
        render_flow_toolbar(board)
        render_composer()
        st.divider()

        view = st.session_state.get("board_view", "flow")
        if view == "flow":
            render_flow_graph(board)
        else:
            render_board_list_view(board)


def render_composer():
    """Universal Task Composer — the primary action point."""
    active_app = st.session_state.get("active_app")
    app_domain = None
    if active_app:
        for d in APP_DOMAINS:
            if d["id"] == active_app:
                app_domain = d
                break

    # Domain badge
    if app_domain:
        st.caption(f"{app_domain['icon']} {app_domain['name']} mode")

    # Suggested prompts
    if app_domain and app_domain.get("prompts"):
        scols = st.columns(len(app_domain["prompts"]))
        for i, prompt in enumerate(app_domain["prompts"]):
            with scols[i]:
                if st.button(prompt, key=f"suggest_{i}", use_container_width=True):
                    st.session_state["composer_prompt"] = prompt
                    st.rerun()

    # Main composer input
    board = st.session_state.get("board")

    with st.form("composer_form", clear_on_submit=True):
        prompt_val = st.session_state.get("composer_prompt", "")
        prompt = st.text_area(
            "Task",
            value=prompt_val,
            placeholder="Describe your task...",
            height=68,
            label_visibility="collapsed",
        )

        cc1, cc2, cc3, cc4 = st.columns([2, 2, 2, 1])
        with cc1:
            model = st.selectbox("Model", MODELS, label_visibility="collapsed",
                                  key="composer_model")
        with cc2:
            # Filter tools by domain if active
            if app_domain:
                domain_tool_names = ["(no tool)"]
                for t in TOOLS:
                    if t["id"] in app_domain.get("tools", []):
                        domain_tool_names.append(t["name"])
                # Also add remaining tools
                for t in TOOLS:
                    if t["name"] not in domain_tool_names:
                        domain_tool_names.append(t["name"])
                tool_list = domain_tool_names
            else:
                tool_list = TOOL_NAMES
            tool = st.selectbox("Tool", tool_list, label_visibility="collapsed",
                                key="composer_tool")
        with cc3:
            output_name = st.text_input("Output", placeholder="output.md",
                                        label_visibility="collapsed", key="composer_output")
        with cc4:
            submitted = st.form_submit_button("▶ Run", use_container_width=True)

        if submitted and prompt.strip():
            st.session_state["composer_prompt"] = ""

            # Resolve tool id
            tool_id = ""
            if tool != "(no tool)":
                for t in TOOLS:
                    if t["name"] == tool:
                        tool_id = t["id"]
                        break

            if board is None:
                # Auto-create a board
                from workflow_models import new_board
                board = new_board("Workspace")
                save_board(board)
                st.session_state["board"] = board

            task = new_task(
                title=prompt.strip()[:80],
                prompt=prompt.strip(),
                tool_id=tool_id,
                model=model,
                output_artifact=output_name.strip() if output_name else "",
            )
            add_task(board, task)

            # Auto-run
            from workflow_models import run_task
            run_task(board, task["id"])
            save_board(board)

            st.session_state["board_selected_task"] = task["id"]
            st.session_state["inspector_mode"] = "task"
            st.rerun()


# ===========================================================================
# RIGHT PANEL: Dynamic Inspector
# ===========================================================================
def render_inspector():
    mode = st.session_state.get("inspector_mode", "none")

    if mode == "task":
        _render_task_inspector()
    elif mode == "file":
        _render_file_inspector()
    elif mode == "folder":
        _render_folder_inspector()
    else:
        _render_empty_inspector()


def _render_empty_inspector():
    st.markdown("### Inspector")
    st.caption("Select an object to inspect:")
    st.markdown(
        "- Click a **file** or **folder** in the left panel\n"
        "- Click a **task node** in the graph\n"
        "- Run a task from the composer"
    )


def _render_task_inspector():
    board = st.session_state.get("board")
    if not board:
        _render_empty_inspector()
        return
    st.markdown('<p class="inspector-header">Task Inspector</p>', unsafe_allow_html=True)
    render_task_detail(board, FILES_DIR)


def _render_file_inspector():
    file_path = st.session_state.get("inspector_file")
    if not file_path:
        _render_empty_inspector()
        return

    fpath = Path(file_path)
    if not fpath.exists():
        st.warning("File not found.")
        return

    # Header
    h1, h2 = st.columns([4, 1])
    with h1:
        is_ai = False
        try:
            head = fpath.read_text(errors="replace")[:50]
            if "<!-- AI Generated" in head:
                is_ai = True
        except Exception:
            pass
        icon = "🤖" if is_ai else "📄"
        st.markdown(f"### {icon} {fpath.name}")
    with h2:
        if st.button("✕", key="file_close"):
            st.session_state["inspector_mode"] = "none"
            st.session_state["inspector_file"] = None
            st.rerun()

    st.caption(f"Path: {fpath.relative_to(FILES_DIR)}")

    # File preview
    content = fpath.read_text(errors="replace")
    with st.expander("Preview", expanded=True):
        if st.session_state.get("editing_file"):
            new_text = st.text_area("Edit", value=content, height=300, key="file_editor",
                                    label_visibility="collapsed")
            ec1, ec2 = st.columns(2)
            with ec1:
                if st.button("💾 Save", key="file_save", use_container_width=True):
                    fpath.write_text(new_text)
                    st.session_state["editing_file"] = False
                    st.toast("File saved!")
                    st.rerun()
            with ec2:
                if st.button("Cancel", key="file_cancel", use_container_width=True):
                    st.session_state["editing_file"] = False
                    st.rerun()
        else:
            st.markdown(content[:3000])
            ec1, ec2, ec3 = st.columns(3)
            with ec1:
                if st.button("✏️ Edit", key="file_edit", use_container_width=True):
                    st.session_state["editing_file"] = True
                    st.rerun()
            with ec2:
                if st.button("📋 Create task", key="file_to_task", use_container_width=True):
                    _create_task_from_file(fpath)
            with ec3:
                if st.button("🗑 Delete", key="file_del", use_container_width=True):
                    fpath.unlink()
                    st.session_state["inspector_mode"] = "none"
                    st.session_state["inspector_file"] = None
                    st.toast("File deleted")
                    st.rerun()

    st.divider()

    # Chat with file
    st.markdown("### 💬 Chat with file")
    _render_chat([fpath])


def _render_folder_inspector():
    folder_path = st.session_state.get("inspector_folder")
    if not folder_path:
        _render_empty_inspector()
        return

    folder = Path(folder_path)
    if not folder.exists():
        st.warning("Folder not found.")
        return

    files = get_files_in_folder(folder)

    # Header
    h1, h2 = st.columns([4, 1])
    with h1:
        st.markdown(f"### 📁 {folder.name}")
    with h2:
        if st.button("✕", key="folder_close"):
            st.session_state["inspector_mode"] = "none"
            st.session_state["inspector_folder"] = None
            st.rerun()

    st.caption(f"{len(files)} file(s)")

    # File list
    if files:
        for f in files:
            fc1, fc2 = st.columns([4, 1])
            with fc1:
                st.caption(f"📄 {f.name}")
            with fc2:
                if st.button("Open", key=f"fopen_{f}", use_container_width=True):
                    _open_file_inspector(str(f))
                    st.rerun()

        if st.button("📋 Create task from folder", key="folder_to_task", use_container_width=True):
            _create_task_from_folder(folder, files)

    st.divider()

    # Chat with folder
    st.markdown("### 💬 Chat with folder")
    _render_chat(files)


def _render_chat(context_files: list[Path]):
    ctx_label = ""
    if len(context_files) == 1:
        ctx_label = f"with {context_files[0].name}"
    elif len(context_files) > 1:
        ctx_label = f"with {len(context_files)} files"
    if ctx_label:
        st.caption(ctx_label)

    st.session_state["selected_model"] = st.selectbox(
        "Model", MODELS,
        index=MODELS.index(st.session_state["selected_model"]),
        label_visibility="collapsed", key="insp_model",
    )

    chat_container = st.container(height=300)
    with chat_container:
        for msg in st.session_state["file_messages"]:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    user_input = st.chat_input("Ask about this...", key="insp_chat_input")
    if user_input:
        st.session_state["file_messages"].append({"role": "user", "content": user_input})
        response = call_llm(user_input, model=st.session_state["selected_model"],
                            context_files=context_files)
        st.session_state["file_messages"].append({"role": "assistant", "content": response})
        st.rerun()

    if st.session_state["file_messages"]:
        bc1, bc2 = st.columns(2)
        with bc1:
            if st.button("🗑 Clear", use_container_width=True, key="insp_clear"):
                st.session_state["file_messages"] = []
                st.rerun()
        with bc2:
            if st.button("📋 → Task", use_container_width=True, key="chat_to_task",
                         help="Create task from chat"):
                _create_task_from_chat(context_files)


def _create_task_from_file(fpath: Path):
    """Create a task with file as input artifact."""
    board = st.session_state.get("board")
    if board is None:
        from workflow_models import new_board
        board = new_board("Workspace")
        save_board(board)
        st.session_state["board"] = board

    task = new_task(
        title=f"Analyze {fpath.name}",
        prompt=f"Analyze the file: {fpath.name}",
        input_artifacts=[str(fpath)],
    )
    add_task(board, task)
    save_board(board)
    st.session_state["board_selected_task"] = task["id"]
    st.session_state["inspector_mode"] = "task"
    st.toast(f"Task created from {fpath.name}")
    st.rerun()


def _create_task_from_folder(folder: Path, files: list[Path]):
    """Create a task with all folder files as input."""
    board = st.session_state.get("board")
    if board is None:
        from workflow_models import new_board
        board = new_board("Workspace")
        save_board(board)
        st.session_state["board"] = board

    task = new_task(
        title=f"Analyze {folder.name}/",
        prompt=f"Analyze all files in folder: {folder.name}",
        input_artifacts=[str(f) for f in files],
    )
    add_task(board, task)
    save_board(board)
    st.session_state["board_selected_task"] = task["id"]
    st.session_state["inspector_mode"] = "task"
    st.toast(f"Task created from {folder.name}/")
    st.rerun()


def _create_task_from_chat(context_files: list[Path]):
    """Create a task from chat conversation."""
    board = st.session_state.get("board")
    if board is None:
        from workflow_models import new_board
        board = new_board("Workspace")
        save_board(board)
        st.session_state["board"] = board

    # Build prompt from chat
    chat_summary = "\n".join(
        f"{'User' if m['role'] == 'user' else 'AI'}: {m['content'][:200]}"
        for m in st.session_state["file_messages"][-4:]  # last 4 messages
    )
    task = new_task(
        title="Task from chat",
        prompt=f"Continue analysis based on conversation:\n\n{chat_summary}",
        input_artifacts=[str(f) for f in context_files],
    )
    add_task(board, task)
    save_board(board)
    st.session_state["board_selected_task"] = task["id"]
    st.session_state["inspector_mode"] = "task"
    st.toast("Task created from chat!")
    st.rerun()


# ===========================================================================
# MAIN LAYOUT
# ===========================================================================

# 1. Top bar — Apps
render_apps_bar()
st.divider()

# 2. Three-column layout
left_visible = st.session_state.get("left_panel_visible", True)

if left_visible:
    left_col, center_col, right_col = st.columns([1.2, 3, 2])
else:
    # Show expand button + center + right
    expand_col, center_col, right_col = st.columns([0.15, 3.5, 2])
    with expand_col:
        if st.button("▶", key="expand_left", help="Show files panel"):
            st.session_state["left_panel_visible"] = True
            st.rerun()

if left_visible:
    with left_col:
        render_file_tree()

with center_col:
    render_center()

with right_col:
    render_inspector()
