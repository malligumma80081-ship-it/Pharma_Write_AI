import requests
import streamlit as st

API_BASE = "http://127.0.0.1:8000/api/v1"

st.set_page_config(
    page_title="PharmaWrite AI",
    page_icon="📄",
    layout="wide",
)

st.title("PharmaWrite AI")
st.caption("Scientific literature review workspace")

project_id = st.text_input("Project ID (integer)")
research_question = st.text_area(
    "Research question",
    placeholder="Summarize study design, outcomes, adverse events, and limitations...",
)

document_ids_text = st.text_area(
    "Document UUIDs",
    placeholder="Paste one existing document UUID per line",
)

top_k = st.slider("Evidence passages to retrieve", 1, 12, 8)

if st.button("Run literature review", type="primary"):
    document_ids = [
        line.strip()
        for line in document_ids_text.splitlines()
        if line.strip()
    ]

    if not project_id or not research_question or not document_ids:
        st.error("Enter the project, research question, and at least one document.")
    else:
        try:
            numeric_project_id = int(project_id.strip())
            if numeric_project_id < 1:
                raise ValueError("Project ID must be positive.")
        except ValueError:
            st.error("Project ID must be a positive integer.")
        else:
            payload = {
                "research_question": research_question,
                "document_ids": document_ids,
                "top_k": top_k,
            }

            try:
                response = requests.post(
                    f"{API_BASE}/projects/{numeric_project_id}/workflows",
                    json=payload,
                    timeout=600,
                )

                if response.ok:
                    result = response.json()
                    st.session_state["workflow_id"] = result["workflow_id"]
                    st.session_state["project_id"] = numeric_project_id
                    st.success(
                        f"Workflow status: {result['status']} — "
                        f"{result['current_stage']}"
                    )
                else:
                    st.error(
                        f"Workflow request failed ({response.status_code}): "
                        f"{response.text}"
                    )
            except requests.RequestException as exc:
                st.error(f"Could not connect to the API: {exc}")

if st.session_state.get("workflow_id"):
    if st.button("Refresh workflow results"):
        try:
            response = requests.get(
                f"{API_BASE}/projects/"
                f"{st.session_state['project_id']}/workflows/"
                f"{st.session_state['workflow_id']}",
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            st.subheader("Workflow status")
            st.write(data["status"], "—", data["current_stage"])

            if data.get("error_message"):
                st.error(data["error_message"])

            result = data.get("result") or {}
            if result:
                st.subheader("Evidence extraction")
                st.json(result.get("evidence", {}))

                st.subheader("Literature draft")
                st.json(result.get("draft", {}))

                st.subheader("Claim verification")
                st.json(result.get("claim_verification", []))

                st.warning(
                    "AI-generated content must be checked against the "
                    "original scientific papers by a qualified reviewer."
                )
        except requests.RequestException as exc:
            st.error(f"Could not load workflow results: {exc}")