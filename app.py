"""AI Workspace — Streamlit MVP v2.

File tree is ALWAYS visible on the left.
Main content area switches between: flow, file_viewer, task_fullscreen.
"""

from pathlib import Path

import streamlit as st
from streamlit_tree_select import tree_select

from flow_page import render_flow_content, render_task_fullscreen
from workflow_models import MODELS

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
    # View routing
    "current_view": "flow",           # "flow" | "file_viewer" | "task_fullscreen"
    "previous_view": "flow",          # for back button
    # File viewer
    "viewing_file": None,             # file path opened from tree
    "viewing_folder": None,           # folder path for folder-chat
    "file_content": "",
    "editing": False,
    "create_new": False,
    # Chat (per-file/folder)
    "file_messages": [],              # chat messages for file viewer
    "selected_model": MODELS[0],
    # Flow
    "board": None,
    "board_selected_task": None,
    "board_view": "flow",
    "board_adding_parent": None,
    "detail_collapsed": False,        # task detail collapsed in flow
}
for key, val in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = val

# ---------------------------------------------------------------------------
# Mock LLM
# ---------------------------------------------------------------------------
def call_llm(prompt: str, model: str = "GPT-4o", context_files: list[Path] | None = None) -> str:
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
st.set_page_config(page_title="AI Workspace", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    [data-testid="stSidebar"] { display: none; }
    .block-container { padding-top: 1rem; padding-bottom: 0; }
    .rct-checkbox { display: none !important; }
    .rct-node-leaf .rct-title { cursor: pointer !important; }
    .rct-node-leaf .rct-title:hover { color: #508cff !important; }
    /* Folder nodes clickable too */
    .rct-node-parent .rct-title { cursor: pointer !important; }
    .rct-node-parent .rct-title:hover { color: #508cff !important; }
    h1 { font-size: 1.3rem !important; margin-bottom: 0 !important; }
    h3 { font-size: 1rem !important; margin-bottom: 0.3rem !important; }
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
            nodes.append({
                "label": f"📄 {item.name}",
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


# ---------------------------------------------------------------------------
# FILE TREE (always rendered on the left)
# ---------------------------------------------------------------------------
def render_file_tree():
    st.markdown("### 📂 Files")

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
                _open_file(str(new_path))
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

    # Tree
    nodes = build_tree_nodes(FILES_DIR)
    if not nodes:
        st.caption("No files yet.")
        return

    prev_checked = []
    if st.session_state.get("viewing_file"):
        prev_checked = [st.session_state["viewing_file"]]

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
            if selected_path != st.session_state.get("viewing_file"):
                _open_file(selected_path)
                st.rerun()
        elif p.is_dir():
            if selected_path != st.session_state.get("viewing_folder"):
                _open_folder(selected_path)
                st.rerun()


def _open_file(file_path: str):
    """Switch to file viewer for a single file."""
    st.session_state["previous_view"] = st.session_state["current_view"]
    st.session_state["current_view"] = "file_viewer"
    st.session_state["viewing_file"] = file_path
    st.session_state["viewing_folder"] = None
    st.session_state["file_content"] = Path(file_path).read_text(errors="replace")
    st.session_state["editing"] = False
    st.session_state["file_messages"] = []


def _open_folder(folder_path: str):
    """Switch to folder chat view."""
    st.session_state["previous_view"] = st.session_state["current_view"]
    st.session_state["current_view"] = "file_viewer"
    st.session_state["viewing_folder"] = folder_path
    st.session_state["viewing_file"] = None
    st.session_state["file_content"] = ""
    st.session_state["editing"] = False
    st.session_state["file_messages"] = []


def _go_back():
    """Return to previous view."""
    prev = st.session_state.get("previous_view", "flow")
    st.session_state["current_view"] = prev
    st.session_state["viewing_file"] = None
    st.session_state["viewing_folder"] = None
    st.session_state["file_messages"] = []


# ---------------------------------------------------------------------------
# FILE VIEWER + CHAT
# ---------------------------------------------------------------------------
def render_file_viewer():
    viewing_file = st.session_state.get("viewing_file")
    viewing_folder = st.session_state.get("viewing_folder")

    # Back button
    if st.button("← Back", key="file_back", use_container_width=False):
        _go_back()
        st.rerun()

    if viewing_folder:
        _render_folder_chat(Path(viewing_folder))
    elif viewing_file:
        _render_single_file(Path(viewing_file))
    else:
        st.info("Select a file or folder from the tree.")


def _render_single_file(fpath: Path):
    if not fpath.exists():
        st.warning("File not found.")
        return

    editor_col, chat_col = st.columns([3, 2])

    with editor_col:
        if not st.session_state["file_content"]:
            st.session_state["file_content"] = fpath.read_text(errors="replace")

        head_l, head_r = st.columns([3, 2])
        with head_l:
            st.markdown(f"### 📝 {fpath.name}")
        with head_r:
            bc = st.columns(3)
            with bc[0]:
                if st.session_state["editing"]:
                    if st.button("💾 Save", use_container_width=True, key="fv_save"):
                        fpath.write_text(st.session_state["file_content"])
                        st.session_state["editing"] = False
                        st.rerun()
                else:
                    if st.button("✏️ Edit", use_container_width=True, key="fv_edit"):
                        st.session_state["editing"] = True
                        st.rerun()
            with bc[1]:
                if st.button("🗑️ Delete", use_container_width=True, key="fv_del"):
                    fpath.unlink()
                    _go_back()
                    st.rerun()
            with bc[2]:
                if st.session_state["editing"]:
                    if st.button("✖ Cancel", use_container_width=True, key="fv_cancel"):
                        st.session_state["file_content"] = fpath.read_text(errors="replace")
                        st.session_state["editing"] = False
                        st.rerun()

        st.divider()

        if st.session_state["editing"]:
            new_text = st.text_area(
                "edit", value=st.session_state["file_content"],
                height=500, key="fv_editor", label_visibility="collapsed",
            )
            st.session_state["file_content"] = new_text
        else:
            st.markdown(st.session_state["file_content"])

    with chat_col:
        _render_chat([fpath])


def _render_folder_chat(folder: Path):
    if not folder.exists():
        st.warning("Folder not found.")
        return

    files = get_files_in_folder(folder)

    files_col, chat_col = st.columns([2, 3])

    with files_col:
        st.markdown(f"### 📁 {folder.name}")
        st.caption(f"{len(files)} file(s)")
        st.divider()
        if files:
            for f in files:
                fc1, fc2 = st.columns([4, 1])
                with fc1:
                    st.caption(f"📄 {f.name}")
                with fc2:
                    if st.button("Open", key=f"fopen_{f}", use_container_width=True):
                        _open_file(str(f))
                        st.rerun()

            # Show combined content preview
            with st.expander("Preview all files", expanded=False):
                for f in files:
                    st.markdown(f"**{f.name}**")
                    try:
                        content = f.read_text(errors="replace")[:1000]
                        st.code(content, language=f.suffix.lstrip(".") or "text")
                    except Exception:
                        st.caption("Cannot read file.")
        else:
            st.caption("Empty folder.")

    with chat_col:
        _render_chat(files)


def _render_chat(context_files: list[Path]):
    st.markdown("### 💬 Chat")

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
        label_visibility="collapsed", key="fv_model",
    )

    st.divider()

    chat_container = st.container(height=420)
    with chat_container:
        for msg in st.session_state["file_messages"]:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    user_input = st.chat_input("Ask about this file…", key="fv_chat_input")
    if user_input:
        st.session_state["file_messages"].append({"role": "user", "content": user_input})
        response = call_llm(user_input, model=st.session_state["selected_model"],
                            context_files=context_files)
        st.session_state["file_messages"].append({"role": "assistant", "content": response})
        st.rerun()

    if st.session_state["file_messages"]:
        if st.button("🗑 Clear chat", use_container_width=True, key="fv_clear_chat"):
            st.session_state["file_messages"] = []
            st.rerun()


# ===========================================================================
# MAIN LAYOUT: [File Tree] + [Content Area]
# ===========================================================================
tree_col, main_col = st.columns([1.2, 5])

with tree_col:
    render_file_tree()

with main_col:
    view = st.session_state["current_view"]

    if view == "file_viewer":
        render_file_viewer()
    elif view == "task_fullscreen":
        render_task_fullscreen(FILES_DIR)
    else:
        # flow view
        render_flow_content(FILES_DIR)
