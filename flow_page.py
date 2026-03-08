"""PlusFlow — workflow builder page for Streamlit."""

from __future__ import annotations

import streamlit as st

from workflow_models import (
    TOOL_CATALOG,
    NodeStatus,
    WorkflowStatus,
    add_next_step,
    add_parallel_step,
    add_start_node,
    delete_node,
    delete_workflow_file,
    get_levels,
    get_root_nodes,
    list_workflows,
    load_workflow,
    new_workflow,
    reset_workflow,
    run_workflow,
    save_workflow,
)

# ---------------------------------------------------------------------------
# Session state keys for flow page
# ---------------------------------------------------------------------------
_FLOW_DEFAULTS = {
    "wf": None,              # current workflow dict
    "wf_selected_node": None, # selected node id
    "wf_adding": None,        # ("next", parent_id) or ("parallel", parent_id)
}

for k, v in _FLOW_DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ---------------------------------------------------------------------------
# Status badge helpers
# ---------------------------------------------------------------------------
_STATUS_COLORS = {
    "draft": "gray",
    "ready": "blue",
    "running": "orange",
    "success": "green",
    "failed": "red",
    "blocked": "yellow",
    "disabled": "gray",
    "partial_success": "orange",
}

_STATUS_ICONS = {
    "draft": "⚪",
    "ready": "🔵",
    "running": "🟠",
    "success": "🟢",
    "failed": "🔴",
    "blocked": "🟡",
    "disabled": "⚫",
    "partial_success": "🟠",
}


def _badge(status: str) -> str:
    icon = _STATUS_ICONS.get(status, "⚪")
    return f"{icon} {status}"


def _tool_name(tool_id: str) -> str:
    for t in TOOL_CATALOG:
        if t["id"] == tool_id:
            return t["name"]
    return "No tool"


# ---------------------------------------------------------------------------
# Render: workflow list (when no workflow is open)
# ---------------------------------------------------------------------------
def _render_workflow_list():
    st.markdown("### Workflows")

    col1, col2 = st.columns([3, 1])
    with col1:
        wf_name = st.text_input("New workflow name", placeholder="My Workflow", label_visibility="collapsed")
    with col2:
        if st.button("+ Create", use_container_width=True):
            name = wf_name.strip() if wf_name else "Untitled Workflow"
            wf = new_workflow(name)
            save_workflow(wf)
            st.session_state["wf"] = wf
            st.rerun()

    st.divider()

    wfs = list_workflows()
    if not wfs:
        st.info("No workflows yet. Create one above.")
        return

    for w in wfs:
        c1, c2, c3 = st.columns([3, 1, 1])
        with c1:
            if st.button(f"{_badge(w['status'])}  {w['name']}", key=f"wf_open_{w['id']}", use_container_width=True):
                loaded = load_workflow(w["id"])
                if loaded:
                    st.session_state["wf"] = loaded
                    st.session_state["wf_selected_node"] = None
                    st.rerun()
        with c2:
            st.caption(w["status"])
        with c3:
            if st.button("🗑", key=f"wf_del_{w['id']}"):
                delete_workflow_file(w["id"])
                st.rerun()


# ---------------------------------------------------------------------------
# Render: single task card
# ---------------------------------------------------------------------------
def _render_node_card(wf: dict, nid: str, indent: int = 0):
    node = wf["nodes"][nid]
    is_selected = st.session_state["wf_selected_node"] == nid
    status = node["status"]

    # Card container
    border_color = {
        "success": "#2ecc71", "failed": "#e74c3c", "running": "#f39c12",
        "blocked": "#f1c40f", "disabled": "#7f8c8d",
    }.get(status, "#508cff" if is_selected else "#444")

    bg = "rgba(80,140,255,0.08)" if is_selected else "rgba(255,255,255,0.02)"

    st.markdown(
        f"""<div style="
            border: 2px solid {border_color};
            border-radius: 8px;
            padding: 12px;
            margin: 4px 0 4px {indent * 20}px;
            background: {bg};
        ">
            <div style="display:flex; align-items:center; gap:8px;">
                <span>{_badge(status)}</span>
                <strong>{node['title']}</strong>
                <span style="color:#888; font-size:0.85em;">— {_tool_name(node['tool_id'])}</span>
            </div>
        </div>""",
        unsafe_allow_html=True,
    )

    # Action buttons row
    cols = st.columns([1, 1, 1, 1, 1])
    with cols[0]:
        if st.button("Select", key=f"sel_{nid}", use_container_width=True):
            st.session_state["wf_selected_node"] = nid
            st.rerun()
    with cols[1]:
        if st.button("+ Next", key=f"add_next_{nid}", use_container_width=True):
            st.session_state["wf_adding"] = ("next", nid)
            st.rerun()
    with cols[2]:
        if st.button("+ Parallel", key=f"add_par_{nid}", use_container_width=True):
            st.session_state["wf_adding"] = ("parallel", nid)
            st.rerun()
    with cols[3]:
        if st.button("🗑", key=f"del_{nid}", use_container_width=True):
            delete_node(wf, nid)
            if st.session_state["wf_selected_node"] == nid:
                st.session_state["wf_selected_node"] = None
            save_workflow(wf)
            st.rerun()
    with cols[4]:
        disabled = node["status"] == NodeStatus.DISABLED.value
        label = "Enable" if disabled else "Disable"
        if st.button(label, key=f"toggle_{nid}", use_container_width=True):
            node["status"] = NodeStatus.DRAFT.value if disabled else NodeStatus.DISABLED.value
            save_workflow(wf)
            st.rerun()


# ---------------------------------------------------------------------------
# Render: DAG as card tree (BFS by levels)
# ---------------------------------------------------------------------------
def _render_dag(wf: dict):
    if not wf["nodes"]:
        st.info("Workflow is empty. Add a start task below.")
        return

    levels = get_levels(wf)
    max_lvl = max(levels.values()) if levels else 0

    for lvl in range(max_lvl + 1):
        nodes_at_level = [nid for nid, l in levels.items() if l == lvl]
        if not nodes_at_level:
            continue

        if lvl > 0:
            # Connection indicator
            st.markdown(
                '<div style="text-align:center; color:#666; font-size:1.2em;">↓</div>',
                unsafe_allow_html=True,
            )

        # Render nodes at this level side by side if multiple (parallel branches)
        if len(nodes_at_level) == 1:
            _render_node_card(wf, nodes_at_level[0])
        else:
            cols = st.columns(len(nodes_at_level))
            for i, nid in enumerate(nodes_at_level):
                with cols[i]:
                    _render_node_card(wf, nid)


# ---------------------------------------------------------------------------
# Render: add-step form
# ---------------------------------------------------------------------------
def _render_add_form(wf: dict):
    adding = st.session_state.get("wf_adding")
    if not adding:
        return

    mode, parent_id = adding
    parent = wf["nodes"].get(parent_id)
    parent_title = parent["title"] if parent else "?"
    label = "next step" if mode == "next" else "parallel step"

    st.markdown(f"**Add {label} after:** {parent_title}")

    with st.form("add_step_form", clear_on_submit=True):
        title = st.text_input("Task title", placeholder="e.g. Summarize PRD")
        tool_options = ["(no tool)"] + [t["name"] for t in TOOL_CATALOG]
        tool_choice = st.selectbox("Tool", tool_options)
        c1, c2 = st.columns(2)
        with c1:
            submitted = st.form_submit_button("Add", use_container_width=True)
        with c2:
            cancelled = st.form_submit_button("Cancel", use_container_width=True)

        if submitted and title.strip():
            tool_id = ""
            if tool_choice != "(no tool)":
                for t in TOOL_CATALOG:
                    if t["name"] == tool_choice:
                        tool_id = t["id"]
                        break
            if mode == "next":
                add_next_step(wf, parent_id, title.strip(), tool_id)
            else:
                add_parallel_step(wf, parent_id, title.strip(), tool_id)
            save_workflow(wf)
            st.session_state["wf_adding"] = None
            st.rerun()

        if cancelled:
            st.session_state["wf_adding"] = None
            st.rerun()


# ---------------------------------------------------------------------------
# Render: node detail panel
# ---------------------------------------------------------------------------
def _render_node_detail(wf: dict):
    nid = st.session_state.get("wf_selected_node")
    if not nid or nid not in wf["nodes"]:
        st.caption("Select a task to see details.")
        return

    node = wf["nodes"][nid]

    st.markdown(f"#### {node['title']}")
    st.caption(f"ID: {nid} | Status: {_badge(node['status'])}")

    # Editable fields
    new_title = st.text_input("Title", value=node["title"], key=f"edit_title_{nid}")
    new_desc = st.text_area("Description", value=node.get("description", ""), key=f"edit_desc_{nid}", height=80)

    tool_names = [t["name"] for t in TOOL_CATALOG]
    current_tool_name = _tool_name(node["tool_id"])
    tool_idx = tool_names.index(current_tool_name) if current_tool_name in tool_names else 0
    new_tool = st.selectbox("Tool", tool_names, index=tool_idx, key=f"edit_tool_{nid}")

    if st.button("Save changes", key=f"save_node_{nid}", use_container_width=True):
        node["title"] = new_title
        node["description"] = new_desc
        for t in TOOL_CATALOG:
            if t["name"] == new_tool:
                node["tool_id"] = t["id"]
                break
        save_workflow(wf)
        st.rerun()

    st.divider()

    # Artifacts
    st.markdown("**Input artifact**")
    if node.get("input_artifact_id") and node["input_artifact_id"] in wf["artifacts"]:
        art = wf["artifacts"][node["input_artifact_id"]]
        with st.expander(f"📥 {art['name']}"):
            st.code(art["content"])
    else:
        st.caption("No input artifact")

    st.markdown("**Output artifact**")
    if node.get("output_artifact_id") and node["output_artifact_id"] in wf["artifacts"]:
        art = wf["artifacts"][node["output_artifact_id"]]
        with st.expander(f"📤 {art['name']}"):
            st.code(art["content"])
    else:
        st.caption("No output artifact")


# ---------------------------------------------------------------------------
# Main render function
# ---------------------------------------------------------------------------
def render_flow_page():
    wf = st.session_state.get("wf")

    if wf is None:
        _render_workflow_list()
        return

    # ---- Toolbar ----
    toolbar = st.columns([0.5, 3, 1, 1, 1, 1])
    with toolbar[0]:
        if st.button("←", key="wf_back", use_container_width=True):
            save_workflow(wf)
            st.session_state["wf"] = None
            st.session_state["wf_selected_node"] = None
            st.session_state["wf_adding"] = None
            st.rerun()
    with toolbar[1]:
        st.markdown(f"### {wf['name']}  {_badge(wf['status'])}")
    with toolbar[2]:
        if not wf["nodes"]:
            pass
        elif st.button("▶ Run", key="wf_run", use_container_width=True):
            reset_workflow(wf)
            run_workflow(wf)
            save_workflow(wf)
            st.rerun()
    with toolbar[3]:
        if wf["nodes"] and st.button("↺ Reset", key="wf_reset", use_container_width=True):
            reset_workflow(wf)
            save_workflow(wf)
            st.rerun()
    with toolbar[4]:
        if st.button("💾 Save", key="wf_save", use_container_width=True):
            save_workflow(wf)
            st.toast("Workflow saved!")
    with toolbar[5]:
        new_name = st.text_input("Rename", value=wf["name"], key="wf_rename", label_visibility="collapsed")
        if new_name != wf["name"]:
            wf["name"] = new_name

    st.divider()

    # ---- Layout: DAG view + Detail panel ----
    dag_col, detail_col = st.columns([3, 1.5])

    with dag_col:
        # Add start task button
        if not wf["nodes"]:
            st.markdown("#### Start building your workflow")
            with st.form("start_form", clear_on_submit=True):
                title = st.text_input("First task title", placeholder="e.g. Collect PRD Input")
                tool_options = ["(no tool)"] + [t["name"] for t in TOOL_CATALOG]
                tool_choice = st.selectbox("Tool", tool_options)
                if st.form_submit_button("+ Add start task", use_container_width=True):
                    if title.strip():
                        tool_id = ""
                        if tool_choice != "(no tool)":
                            for t in TOOL_CATALOG:
                                if t["name"] == tool_choice:
                                    tool_id = t["id"]
                                    break
                        add_start_node(wf, title.strip(), tool_id)
                        save_workflow(wf)
                        st.rerun()
        else:
            _render_dag(wf)
            st.markdown("---")
            _render_add_form(wf)

    with detail_col:
        st.markdown("#### Task details")
        _render_node_detail(wf)
