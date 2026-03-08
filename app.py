"""AI Workspace — Streamlit MVP"""

import os
from pathlib import Path

import streamlit as st
from streamlit_tree_select import tree_select

from flow_page import render_flow_page

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
WORKSPACE = Path(__file__).parent / "workspace"
FILES_DIR = WORKSPACE / "files"
FILES_DIR.mkdir(parents=True, exist_ok=True)

MODELS = ["GPT-4o", "GPT-4o mini", "Claude Sonnet", "Claude Haiku"]

# ---------------------------------------------------------------------------
# Session state defaults
# ---------------------------------------------------------------------------
DEFAULTS = {
    "messages": [],
    "selected_model": MODELS[0],
    "selected_file": None,
    "file_content": "",
    "editing": False,
    "create_new": False,
    "current_page": "files",  # "files" or "flow"
}
for key, val in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = val

# ---------------------------------------------------------------------------
# Mock LLM
# ---------------------------------------------------------------------------
def call_llm(prompt: str, model: str = "GPT-4o") -> str:
    return (
        f"**[{model}]** Here is my response:\n\n"
        f"You asked: *{prompt[:120]}{'…' if len(prompt) > 120 else ''}*\n\n"
        "1. **Point A** — This is an important observation.\n"
        "2. **Point B** — Consider this factor.\n"
        "3. **Point C** — Worth exploring further.\n\n"
        "Let me know if you'd like to dive deeper."
    )

# ---------------------------------------------------------------------------
# Page config & custom CSS
# ---------------------------------------------------------------------------
st.set_page_config(page_title="AI Workspace", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    /* Hide default sidebar */
    [data-testid="stSidebar"] { display: none; }

    /* Tighter padding */
    .block-container { padding-top: 1rem; padding-bottom: 0; }

    /* Hide checkboxes in tree select — click-to-select only */
    .rct-checkbox { display: none !important; }

    /* Tree node styling */
    .rct-node-leaf .rct-title {
        cursor: pointer !important;
    }
    .rct-node-leaf .rct-title:hover {
        color: #508cff !important;
    }

    /* Compact header */
    h1 { font-size: 1.3rem !important; margin-bottom: 0 !important; }
    h3 { font-size: 1rem !important; margin-bottom: 0.3rem !important; }

    /* Nav toggle buttons */
    .nav-active > button {
        background: rgba(80, 140, 255, 0.25) !important;
        border-bottom: 3px solid #508cff !important;
        font-weight: 600 !important;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Navigation bar
# ---------------------------------------------------------------------------
nav_cols = st.columns([1, 1, 6])
with nav_cols[0]:
    files_css = "nav-active" if st.session_state["current_page"] == "files" else ""
    st.markdown(f'<div class="{files_css}">', unsafe_allow_html=True)
    if st.button("📂 Files", key="nav_files", use_container_width=True):
        st.session_state["current_page"] = "files"
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
with nav_cols[1]:
    flow_css = "nav-active" if st.session_state["current_page"] == "flow" else ""
    st.markdown(f'<div class="{flow_css}">', unsafe_allow_html=True)
    if st.button("⚡ Flow", key="nav_flow", use_container_width=True):
        st.session_state["current_page"] = "flow"
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

st.divider()

# ---------------------------------------------------------------------------
# Helper: build tree nodes for streamlit_tree_select
# ---------------------------------------------------------------------------
def build_tree_nodes(base: Path) -> list[dict]:
    """Build nested node list for tree_select component."""
    nodes = []
    if not base.exists():
        return nodes
    for item in sorted(base.iterdir()):
        if item.name.startswith("."):
            continue
        if item.is_dir():
            children = build_tree_nodes(item)
            if children:
                nodes.append({
                    "label": f"📁 {item.name}",
                    "value": str(item),
                    "children": children,
                })
        else:
            nodes.append({
                "label": f"📄 {item.name}",
                "value": str(item),
            })
    return nodes

# ===========================================================================
# PAGE ROUTING
# ===========================================================================
if st.session_state["current_page"] == "flow":
    render_flow_page(FILES_DIR)
else:
    # ---------------------------------------------------------------------------
    # LAYOUT: 3 columns — File Tree | Editor | Chat
    # ---------------------------------------------------------------------------
    tree_col, editor_col, chat_col = st.columns([1.2, 3, 1.5])

    # ========================== LEFT: FILE TREE ================================
    with tree_col:
        st.markdown("### 📂 Files")

        # New file button
        if st.button("＋ New file", key="new_file_btn", use_container_width=True):
            st.session_state["create_new"] = True
            st.session_state["editing"] = False

        # New file form
        if st.session_state.get("create_new"):
            with st.form("create_form", clear_on_submit=True):
                new_name = st.text_input("File name", placeholder="notes.md")
                col_ok, col_cancel = st.columns(2)
                with col_ok:
                    submitted = st.form_submit_button("Create")
                with col_cancel:
                    cancelled = st.form_submit_button("Cancel")

                if submitted and new_name:
                    if not new_name.endswith(".md"):
                        new_name += ".md"
                    new_path = FILES_DIR / new_name
                    new_path.write_text(f"# {new_name.replace('.md', '')}\n\n")
                    st.session_state["selected_file"] = str(new_path)
                    st.session_state["file_content"] = new_path.read_text()
                    st.session_state["create_new"] = False
                    st.session_state["editing"] = True
                    st.rerun()
                if cancelled:
                    st.session_state["create_new"] = False
                    st.rerun()

        st.divider()

        # Tree select component
        nodes = build_tree_nodes(FILES_DIR)
        if nodes:
            prev_checked = []
            if st.session_state["selected_file"]:
                prev_checked = [st.session_state["selected_file"]]

            result = tree_select(
                nodes,
                check_model="leaf",
                checked=prev_checked,
                expanded=[str(FILES_DIR)],
                expand_on_click=True,
                only_leaf_checkboxes=True,
                no_cascade=True,
            )

            checked = result.get("checked", [])
            if checked:
                new_selection = checked[-1]
                if new_selection != st.session_state["selected_file"]:
                    fpath = Path(new_selection)
                    if fpath.is_file():
                        st.session_state["selected_file"] = str(fpath)
                        st.session_state["file_content"] = fpath.read_text(errors="replace")
                        st.session_state["editing"] = False
                        st.session_state["create_new"] = False
                        st.rerun()
            elif not checked and st.session_state["selected_file"]:
                st.session_state["selected_file"] = None
                st.session_state["file_content"] = ""
                st.session_state["editing"] = False
                st.rerun()
        else:
            st.caption("No files yet. Create one above.")

    # ========================== CENTER: EDITOR =================================
    with editor_col:
        if st.session_state["selected_file"]:
            fpath = Path(st.session_state["selected_file"])

            if not fpath.exists():
                st.warning("File not found.")
            else:
                if not st.session_state["file_content"]:
                    st.session_state["file_content"] = fpath.read_text(errors="replace")

                head_left, head_right = st.columns([3, 2])
                with head_left:
                    st.markdown(f"### 📝 {fpath.name}")
                with head_right:
                    btn_cols = st.columns(3)
                    with btn_cols[0]:
                        if st.session_state["editing"]:
                            if st.button("💾 Save", use_container_width=True):
                                fpath.write_text(st.session_state["file_content"])
                                st.session_state["editing"] = False
                                st.rerun()
                        else:
                            if st.button("✏️ Edit", use_container_width=True):
                                st.session_state["editing"] = True
                                st.rerun()
                    with btn_cols[1]:
                        if st.button("🗑️ Delete", use_container_width=True):
                            fpath.unlink()
                            st.session_state["selected_file"] = None
                            st.session_state["file_content"] = ""
                            st.session_state["editing"] = False
                            st.rerun()
                    with btn_cols[2]:
                        if st.session_state["editing"]:
                            if st.button("✖ Cancel", use_container_width=True):
                                st.session_state["file_content"] = fpath.read_text(errors="replace")
                                st.session_state["editing"] = False
                                st.rerun()

                st.divider()

                if st.session_state["editing"]:
                    new_text = st.text_area(
                        "edit",
                        value=st.session_state["file_content"],
                        height=500,
                        key="editor_area",
                        label_visibility="collapsed",
                    )
                    st.session_state["file_content"] = new_text
                else:
                    st.markdown(st.session_state["file_content"])
        else:
            st.markdown("### Welcome to AI Workspace")
            st.info("← Select a file from the tree or create a new one.")

    # ========================== RIGHT: CHAT ====================================
    with chat_col:
        st.markdown("### 💬 Chat")

        st.session_state["selected_model"] = st.selectbox(
            "Model",
            MODELS,
            index=MODELS.index(st.session_state["selected_model"]),
            label_visibility="collapsed",
        )

        st.divider()

        chat_container = st.container(height=420)
        with chat_container:
            for msg in st.session_state["messages"]:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])

        user_input = st.chat_input("Ask anything…", key="chat_input")
        if user_input:
            context_note = ""
            if st.session_state["selected_file"] and st.session_state["file_content"]:
                fname = Path(st.session_state["selected_file"]).name
                context_note = f" (context: {fname})"

            st.session_state["messages"].append({
                "role": "user",
                "content": user_input + context_note,
            })
            response = call_llm(user_input, model=st.session_state["selected_model"])
            st.session_state["messages"].append({"role": "assistant", "content": response})
            st.rerun()

        if st.session_state["messages"]:
            if st.button("🗑 Clear chat", use_container_width=True, key="clear_chat"):
                st.session_state["messages"] = []
                st.rerun()
