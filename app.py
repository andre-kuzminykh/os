"""AI Workspace — Streamlit MVP (v0.2)"""

import json
import os
from pathlib import Path

import streamlit as st

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
WORKSPACE = Path(__file__).parent / "workspace"
FILES_DIR = WORKSPACE / "files"
ARTIFACTS_DIR = WORKSPACE / "artifacts"
PIPELINES_DIR = WORKSPACE / "pipelines"
INTEGRATIONS_DIR = WORKSPACE / "integrations"

MODELS = ["GPT-5.2", "GPT-4o"]

# Ensure directories exist
for d in (FILES_DIR, ARTIFACTS_DIR, PIPELINES_DIR, INTEGRATIONS_DIR):
    d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Session state defaults
# ---------------------------------------------------------------------------
DEFAULTS = {
    "messages": [],
    "selected_model": MODELS[0],
    "selected_file": None,
    "selected_folder": None,
    "github_connected": False,
    "confluence_connected": False,
    "show_pipeline_builder": False,
    "pipelines": {},
}

for key, val in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = val

# Load saved pipelines from disk
if not st.session_state["pipelines"]:
    for p in PIPELINES_DIR.glob("*.json"):
        st.session_state["pipelines"][p.stem] = json.loads(p.read_text())


# ---------------------------------------------------------------------------
# Helper: mock LLM call
# ---------------------------------------------------------------------------
def call_llm(prompt: str, context: str = "", model: str = "GPT-5.2") -> str:
    """Mock LLM response. Replace with real OpenAI call when ready."""
    ctx_note = ""
    if context:
        ctx_note = f"\n\n*(Based on provided context of {len(context)} chars)*"
    return (
        f"**[{model}]** Here is my analysis:\n\n"
        f"You asked: *{prompt[:120]}{'…' if len(prompt) > 120 else ''}*\n\n"
        "Based on my analysis, here are the key points:\n\n"
        "1. **Insight A** — This is an important observation related to your question.\n"
        "2. **Insight B** — Consider this factor when making decisions.\n"
        "3. **Insight C** — This could be a valuable area to explore further.\n\n"
        f"Let me know if you'd like me to dive deeper into any of these areas.{ctx_note}"
    )


# ---------------------------------------------------------------------------
# Helper: build file tree dict
# ---------------------------------------------------------------------------
def build_tree(base: Path, prefix: str = "") -> dict:
    """Return nested dict representing directory tree."""
    tree: dict = {}
    if not base.exists():
        return tree
    for item in sorted(base.iterdir()):
        if item.name.startswith("."):
            continue
        if item.is_dir():
            tree[item.name] = {"_type": "folder", "_path": str(item), "children": build_tree(item)}
        else:
            tree[item.name] = {"_type": "file", "_path": str(item)}
    return tree


def render_tree(tree: dict, indent: int = 0):
    """Render file tree in sidebar with expandable folders."""
    for name, info in tree.items():
        if info["_type"] == "folder":
            with st.sidebar.expander(f"{'  ' * indent}📁 {name}", expanded=(indent < 1)):
                for child_name, child_info in info.get("children", {}).items():
                    if child_info["_type"] == "folder":
                        render_tree({child_name: child_info}, indent + 1)
                    else:
                        if st.button(f"📄 {child_name}", key=f"file_{child_info['_path']}"):
                            st.session_state["selected_file"] = child_info["_path"]
                            st.session_state["selected_folder"] = info["_path"]
        else:
            if st.sidebar.button(f"{'  ' * indent}📄 {name}", key=f"file_{info['_path']}"):
                st.session_state["selected_file"] = info["_path"]


# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(page_title="AI Workspace", layout="wide")

# ---------------------------------------------------------------------------
# HEADER
# ---------------------------------------------------------------------------
header_cols = st.columns([3, 1, 1])
with header_cols[0]:
    st.title("AI Workspace")
with header_cols[1]:
    st.session_state["selected_model"] = st.selectbox(
        "Model", MODELS, index=MODELS.index(st.session_state["selected_model"])
    )
with header_cols[2]:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🔗 New Task Sequence"):
        st.session_state["show_pipeline_builder"] = True

st.divider()

# ---------------------------------------------------------------------------
# SIDEBAR — Knowledge Tree
# ---------------------------------------------------------------------------
st.sidebar.header("Knowledge Tree")

# --- My Files ---
st.sidebar.subheader("My Files")
my_files_tree = build_tree(FILES_DIR)
for name, info in my_files_tree.items():
    if info["_type"] == "file":
        if st.sidebar.button(f"📄 {name}", key=f"myfile_{info['_path']}"):
            st.session_state["selected_file"] = info["_path"]
            st.session_state["selected_folder"] = str(FILES_DIR)

# --- LLM Artifacts ---
st.sidebar.subheader("LLM Artifacts")
artifacts_tree = build_tree(ARTIFACTS_DIR)
if artifacts_tree:
    for name, info in artifacts_tree.items():
        if info["_type"] == "file":
            if st.sidebar.button(f"📄 {name}", key=f"artifact_{info['_path']}"):
                st.session_state["selected_file"] = info["_path"]
                st.session_state["selected_folder"] = str(ARTIFACTS_DIR)
else:
    st.sidebar.caption("No artifacts yet")

# --- Integrations ---
st.sidebar.subheader("Integrations")

# GitHub
if st.session_state["github_connected"]:
    with st.sidebar.expander("📁 GitHub / repo_name", expanded=False):
        gh_tree = build_tree(INTEGRATIONS_DIR / "github")
        for name, info in gh_tree.items():
            if info["_type"] == "file":
                if st.sidebar.button(f"📄 {name}", key=f"gh_{info['_path']}"):
                    st.session_state["selected_file"] = info["_path"]
                    st.session_state["selected_folder"] = str(INTEGRATIONS_DIR / "github")
else:
    if st.sidebar.button("+ Connect GitHub"):
        st.session_state["github_connected"] = True
        st.rerun()

# Confluence
if st.session_state["confluence_connected"]:
    with st.sidebar.expander("📁 Confluence / AI Transformation", expanded=False):
        cf_tree = build_tree(INTEGRATIONS_DIR / "confluence")
        for name, info in cf_tree.items():
            if info["_type"] == "file":
                if st.sidebar.button(f"📄 {name}", key=f"cf_{info['_path']}"):
                    st.session_state["selected_file"] = info["_path"]
                    st.session_state["selected_folder"] = str(INTEGRATIONS_DIR / "confluence")
else:
    if st.sidebar.button("+ Connect Confluence"):
        st.session_state["confluence_connected"] = True
        st.rerun()

# --- Pipelines ---
st.sidebar.subheader("Task Sequences")
if st.session_state["pipelines"]:
    for pname in st.session_state["pipelines"]:
        if st.sidebar.button(f"📄 {pname}", key=f"pipeline_{pname}"):
            st.session_state["selected_pipeline_run"] = pname
else:
    st.sidebar.caption("No pipelines yet")

# --- Upload ---
st.sidebar.divider()
uploaded = st.sidebar.file_uploader("Upload file", type=["txt", "md", "pdf"])
if uploaded is not None:
    dest = FILES_DIR / uploaded.name
    dest.write_bytes(uploaded.getvalue())
    st.sidebar.success(f"Saved {uploaded.name}")
    st.rerun()

# ---------------------------------------------------------------------------
# MAIN AREA  —  3-column layout: Chat | File Viewer
# ---------------------------------------------------------------------------

# Check if pipeline builder should be shown
if st.session_state.get("show_pipeline_builder"):
    # -----------------------------------------------------------------------
    # Pipeline Builder
    # -----------------------------------------------------------------------
    st.subheader("Task Sequence Builder")

    with st.form("pipeline_form"):
        seq_name = st.text_input("Sequence name", "Product Research Pipeline")

        st.markdown("---")
        num_tasks = st.number_input("Number of tasks", min_value=1, max_value=10, value=2)

        tasks = []
        for i in range(int(num_tasks)):
            st.markdown(f"**Task {i + 1}**")
            prompt = st.text_area(f"Prompt (task {i + 1})", key=f"task_prompt_{i}", height=80)
            if i == 0:
                # Gather available files for context selection
                available_files = []
                for d in (FILES_DIR, ARTIFACTS_DIR):
                    for f in d.rglob("*"):
                        if f.is_file():
                            available_files.append(str(f))
                ctx_file = st.selectbox(
                    f"Input context (task {i + 1})",
                    ["None"] + available_files,
                    key=f"task_ctx_{i}",
                )
            else:
                ctx_file = st.selectbox(
                    f"Input context (task {i + 1})",
                    [f"Artifact from task {i}", "None"],
                    key=f"task_ctx_{i}",
                )
            tasks.append({"prompt": prompt, "context": ctx_file})
            st.markdown("---")

        submitted = st.form_submit_button("Save Sequence")
        if submitted and seq_name:
            pipeline_data = {"name": seq_name, "tasks": tasks}
            st.session_state["pipelines"][seq_name] = pipeline_data
            save_path = PIPELINES_DIR / f"{seq_name}.json"
            save_path.write_text(json.dumps(pipeline_data, indent=2))
            st.success(f"Pipeline '{seq_name}' saved!")
            st.session_state["show_pipeline_builder"] = False
            st.rerun()

    if st.button("Cancel"):
        st.session_state["show_pipeline_builder"] = False
        st.rerun()

elif st.session_state.get("selected_pipeline_run"):
    # -----------------------------------------------------------------------
    # Pipeline Runner
    # -----------------------------------------------------------------------
    pname = st.session_state["selected_pipeline_run"]
    pipeline = st.session_state["pipelines"].get(pname, {})

    st.subheader(f"Run Pipeline: {pname}")
    st.json(pipeline)

    # Select input file
    available_files = []
    for d in (FILES_DIR, ARTIFACTS_DIR):
        for f in d.rglob("*"):
            if f.is_file():
                available_files.append(str(f))

    input_file = st.selectbox("Input file", ["None"] + available_files)

    if st.button("▶ Run Pipeline"):
        tasks = pipeline.get("tasks", [])
        prev_artifact = ""
        if input_file and input_file != "None":
            prev_artifact = Path(input_file).read_text(errors="replace")

        for i, task in enumerate(tasks):
            st.markdown(f"### Task {i + 1}: {task['prompt'][:60]}")
            with st.spinner(f"Running task {i + 1}..."):
                context = prev_artifact if prev_artifact else ""
                response = call_llm(task["prompt"], context, st.session_state["selected_model"])
                st.markdown(response)

                # Save artifact
                artifact_name = f"{pname}_step{i + 1}.md"
                artifact_path = ARTIFACTS_DIR / artifact_name
                artifact_path.write_text(response)
                prev_artifact = response
                st.caption(f"Saved artifact: {artifact_name}")

        st.success("Pipeline complete!")

    if st.button("← Back to chat"):
        st.session_state["selected_pipeline_run"] = None
        st.rerun()

else:
    # -----------------------------------------------------------------------
    # Chat + File Viewer (default view)
    # -----------------------------------------------------------------------
    chat_col, viewer_col = st.columns([3, 2])

    # --- Main Chat ---
    with chat_col:
        st.subheader("Chat")

        # Display messages
        chat_container = st.container(height=450)
        with chat_container:
            for msg in st.session_state["messages"]:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])

        # Chat input
        user_input = st.chat_input("Write message...")
        if user_input:
            st.session_state["messages"].append({"role": "user", "content": user_input})
            response = call_llm(user_input, model=st.session_state["selected_model"])
            st.session_state["messages"].append({"role": "assistant", "content": response})
            st.rerun()

        # Save last assistant message as artifact
        if st.session_state["messages"]:
            last_msg = st.session_state["messages"][-1]
            if last_msg["role"] == "assistant":
                save_cols = st.columns([3, 1])
                with save_cols[1]:
                    if st.button("💾 Save as artifact"):
                        idx = len(list(ARTIFACTS_DIR.glob("*.md"))) + 1
                        artifact_name = f"artifact_{idx}.md"
                        (ARTIFACTS_DIR / artifact_name).write_text(last_msg["content"])
                        st.success(f"Saved as {artifact_name}")
                        st.rerun()

    # --- File Viewer ---
    with viewer_col:
        st.subheader("File Viewer")

        if st.session_state["selected_file"]:
            fpath = Path(st.session_state["selected_file"])
            if fpath.exists():
                st.caption(f"**{fpath.name}**")
                content = fpath.read_text(errors="replace")
                st.text_area("", content, height=350, disabled=True, key="file_content_viewer")

                st.markdown("**Ask about:**")
                ask_scope = st.radio(
                    "Context scope",
                    ["This file", "Entire folder"],
                    horizontal=True,
                    label_visibility="collapsed",
                )

                ask_question = st.text_input("Your question about this file", key="file_question")
                if st.button("Ask AI", key="ask_ai_file"):
                    if ask_question:
                        if ask_scope == "This file":
                            ctx = content
                        else:
                            # Gather all files in the folder
                            folder = Path(st.session_state.get("selected_folder", fpath.parent))
                            parts = []
                            for f in folder.rglob("*"):
                                if f.is_file():
                                    parts.append(f"--- {f.name} ---\n{f.read_text(errors='replace')}")
                            ctx = "\n\n".join(parts)

                        response = call_llm(ask_question, ctx, st.session_state["selected_model"])
                        st.session_state["messages"].append(
                            {"role": "user", "content": f"[About {fpath.name}] {ask_question}"}
                        )
                        st.session_state["messages"].append({"role": "assistant", "content": response})
                        st.rerun()
            else:
                st.warning("File not found")
        else:
            st.info("Select a file from the sidebar to view it here.")
