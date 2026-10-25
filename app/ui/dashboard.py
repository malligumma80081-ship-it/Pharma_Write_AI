import json
import sys
from pathlib import Path

import requests
import streamlit as st

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from .api_client import (  # type: ignore[import-not-found]
        APIError,
        download_export,
        get_current_user,
        get_ollama_status,
        get_review,
        get_review_queue,
        get_workflow,
        login,
        register,
        record_decision,
        save_review,
        start_workflow,
        submit_for_review,
        upload_pdf,
    )
except ImportError:
    from api_client import (
        APIError,
        download_export,
        get_current_user,
        get_ollama_status,
        get_review,
        get_review_queue,
        get_workflow,
        login,
        register,
        record_decision,
        save_review,
        start_workflow,
        submit_for_review,
        upload_pdf,
    )

st.set_page_config(
    page_title="PharmaWrite AI",
    page_icon="🧬",
    layout="wide",
)

st.title("🧬 PharmaWrite AI")
st.caption("Scientific Literature Workspace")


def clear_auth_state():
    for key in (
        "access_token",
        "authenticated_user",
        "project_id",
        "workflow_uuid",
        "created_workflow_id",
        "created_workflow_project_id",
        "review_data",
        "export_pdf",
        "export_docx",
    ):
        st.session_state.pop(key, None)


if not st.session_state.get("access_token"):
    sign_in_tab, register_tab = st.tabs(["Sign in", "Create account"])

    with sign_in_tab:
        with st.form("login_form"):
            login_email = st.text_input("Email address", key="login_email")
            login_password = st.text_input(
                "Password",
                type="password",
                key="login_password",
            )
            login_submitted = st.form_submit_button("Sign in", type="primary")

        if login_submitted:
            try:
                token_response = login(login_email.strip(), login_password)
                if token_response is None:
                    raise KeyError("access_token")
                token = token_response["access_token"]
                user = get_current_user(token)
                st.session_state["access_token"] = token
                st.session_state["authenticated_user"] = user
                st.rerun()
            except (APIError, KeyError) as exc:
                st.error(f"Sign in failed: {exc}")

    with register_tab:
        st.caption("New accounts are registered with the Writer role.")
        with st.form("register_form"):
            register_email = st.text_input(
                "Email address",
                key="register_email",
            )
            register_password = st.text_input(
                "Password (at least 12 characters)",
                type="password",
                key="register_password",
            )
            confirm_password = st.text_input(
                "Confirm password",
                type="password",
                key="confirm_password",
            )
            register_submitted = st.form_submit_button(
                "Create account",
                type="primary",
            )

        if register_submitted:
            if register_password != confirm_password:
                st.error("The passwords do not match.")
            else:
                try:
                    created_user = register(
                        register_email.strip(),
                        register_password,
                    )
                    st.success(
                        f"Account created for {register_email.strip()}. "
                        "Sign in to continue."
                    )
                except APIError as exc:
                    st.error(f"Could not create account: {exc}")
    st.stop()

access_token = st.session_state["access_token"]
try:
    current_user = get_current_user(access_token)
except APIError as exc:
    clear_auth_state()
    st.error(f"Your session is no longer valid. Please sign in again. {exc}")
    st.stop()

if not isinstance(current_user, dict):
    clear_auth_state()
    st.error("Your session is no longer valid. Please sign in again.")
    st.stop()

role = current_user.get("role")
role_pages = {
    "writer": [
        "Overview",
        "Documents",
        "Generate Draft",
        "Summary & Submit",
        "PDF Download",
        "Word Download",
    ],
    "reviewer": [
        "Overview",
        "Team Lead Queue",
        "Review & Export",
        "PDF Download",
        "Word Download",
    ],
    "admin": [
        "Overview",
        "Documents",
        "Generate Draft",
        "Summary & Submit",
        "Team Lead Queue",
        "Review & Export",
        "PDF Download",
        "Word Download",
    ],
}
if role not in role_pages:
    st.error("Your account has no recognized role. Contact an administrator.")
    st.stop()

st.sidebar.title("Workspace")
st.sidebar.caption(f"{current_user['email']} · {role.title()}")
if st.sidebar.button("Log out"):
    clear_auth_state()
    st.rerun()

page = st.sidebar.radio(
    "Navigation",
    role_pages[role],
    key="navigation",
)

st.sidebar.info(
    "AI-generated scientific content must be reviewed by a qualified human "
    "before external use."
)

if st.sidebar.button("Check AI connection"):
    try:
        ollama_status = get_ollama_status()
        if ollama_status["status"] == "connected":
            st.sidebar.success("AI service: Connected")
            if ollama_status["model_available"]:
                st.sidebar.caption(
                    f"Model {ollama_status['model']} is available."
                )
            else:
                st.sidebar.warning(
                    f"Connected, but model {ollama_status['model']} "
                    "is not installed."
                )
        else:
            st.sidebar.error("AI service: Disconnected")
    except APIError as exc:
        st.sidebar.error(f"Could not check AI service: {exc}")

project_id = st.sidebar.text_input(
    "Project ID (integer)",
    key="project_id",
).strip()
workflow_id = st.sidebar.text_input("Workflow UUID", key="workflow_uuid").strip()


def show_api_error(exc: APIError):
    st.error(str(exc))


def show_ollama_status(container):
    try:
        ollama_status = get_ollama_status()
    except APIError as exc:
        container.error(f"Could not check AI service: {exc}")
        return

    if ollama_status["status"] != "connected":
        container.error("AI service: Disconnected")
    elif ollama_status["model_available"]:
        container.success(
            f"AI service: Connected · Model {ollama_status['model']} available"
        )
    else:
        container.warning(
            f"AI service: Connected, but model {ollama_status['model']} "
            "is not installed."
        )


def select_queue_workflow(item):
    st.session_state["project_id"] = str(item["project_id"])
    st.session_state["workflow_uuid"] = item["workflow_id"]
    st.session_state["navigation"] = "Review & Export"


def select_created_workflow():
    st.session_state["project_id"] = st.session_state[
        "created_workflow_project_id"
    ]
    st.session_state["workflow_uuid"] = st.session_state[
        "created_workflow_id"
    ]


def render_download_page(file_format: str):
    label = "PDF" if file_format == "pdf" else "Word document"
    st.subheader(f"Download {label}")

    if not project_id or not workflow_id:
        st.info("Enter the project ID and workflow UUID in the sidebar.")
        return

    try:
        workflow = get_workflow(project_id, workflow_id, access_token)
    except APIError as exc:
        show_api_error(exc)
        return

    if not isinstance(workflow, dict):
        st.error("Could not load workflow details.")
        return

    review_status = workflow.get("review_status")
    st.caption(
        f"Workflow: {workflow.get('status', 'unknown')} · "
        f"Review: {review_status or 'pending_human_review'}"
    )
    if review_status != "approved":
        st.info(
            "Downloads are available after the Team Lead approves the summary."
        )
        return

    mime_type = (
        "application/pdf"
        if file_format == "pdf"
        else (
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document"
        )
    )
    if st.button(f"Prepare {label}", type="primary"):
        try:
            response = download_export(
                project_id,
                workflow_id,
                file_format,
                access_token,
            )
            response.raise_for_status()
            st.session_state[f"approved_export_{file_format}"] = response.content
        except requests.RequestException as exc:
            st.error(f"Could not prepare the {label} download: {exc}")

    data = st.session_state.get(f"approved_export_{file_format}")
    if data:
        st.download_button(
            f"Download {label}",
            data=data,
            file_name=f"pharmawrite_review.{file_format}",
            mime=mime_type,
            key=f"approved_download_{file_format}",
        )


if page == "Overview":
    st.subheader("Project overview")

    if not project_id:
        st.info("Enter an existing project ID in the sidebar to get started.")
    else:
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Selected project", project_id[:12] + "..." if len(project_id) > 12 else project_id)
        with col2:
            st.metric(
                "Workflow",
                workflow_id[:12] + "..." if workflow_id and len(workflow_id) > 12 else (workflow_id or "Not selected"),
            )

        st.markdown("### Workflow summary")
        st.write(
            "Upload PDFs → Generate a draft → Review evidence → "
            "Approve or revise → Export PDF/DOCX."
        )

        if workflow_id and st.button("Refresh workflow status"):
            try:
                result = get_workflow(project_id, workflow_id, access_token)
                st.json(result)
            except APIError as exc:
                show_api_error(exc)

elif page == "Documents":
    st.subheader("Document management")

    if not project_id:
        st.warning("Enter a project ID in the sidebar before uploading files.")
    else:
        uploaded_files = st.file_uploader(
            "Upload scientific PDF documents",
            type=["pdf"],
            accept_multiple_files=True,
        )

        if st.button("Upload selected PDFs", type="primary"):
            if not uploaded_files:
                st.warning("Select at least one PDF to upload.")
            else:
                for uploaded_file in uploaded_files:
                    try:
                        result = upload_pdf(
                            project_id,
                            uploaded_file,
                            access_token,
                        )
                        st.success(f"Uploaded: {uploaded_file.name}")
                        st.json(result)
                    except APIError as exc:
                        st.error(f"{uploaded_file.name}: {exc}")

        st.caption(
            "After upload, use the returned document IDs when you create a workflow."
        )

elif page == "Generate Draft":
    st.subheader("Generate an evidence-grounded draft")

    if not project_id:
        st.warning("Enter a project ID in the sidebar before creating a workflow.")
    else:
        question = st.text_area(
            "Research question",
            placeholder=(
                "Enter any research question or topic to investigate using "
                "the selected documents."
            ),
            height=120,
        )

        document_ids_text = st.text_area(
            "Document UUIDs (one per line)",
            placeholder="Paste document IDs returned after upload",
        )

        top_k = st.slider(
            "Evidence passages to retrieve",
            min_value=1,
            max_value=15,
            value=8,
        )

        if st.button("Generate literature draft", type="primary"):
            document_ids = [
                value.strip()
                for value in document_ids_text.splitlines()
                if value.strip()
            ]

            if not question.strip():
                st.warning("Enter a research question.")
            elif not document_ids:
                st.warning("Enter at least one document UUID.")
            else:
                try:
                    with st.spinner("Generating draft..."):
                        result = start_workflow(
                            project_id=project_id,
                            research_question=question.strip(),
                            document_ids=document_ids,
                            token=access_token,
                            top_k=top_k,
                        ) or {}

                    new_id = result.get("workflow_id") or result.get("id")
                    if new_id:
                        st.session_state["created_workflow_id"] = str(new_id)
                        st.session_state["created_workflow_project_id"] = str(
                            project_id
                        )
                    if result.get("status") == "completed":
                        st.success(
                            "Workflow completed. Human review is required."
                        )
                    else:
                        st.error(
                            f"Workflow status: {result.get('status', 'unknown')} "
                            f"· Current stage: "
                            f"{result.get('current_stage', 'unknown')}"
                        )
                        show_ollama_status(st)
                        st.info(
                            "A failed workflow cannot be changed to connected. "
                            "Check the AI connection, then run a new workflow."
                        )

                    if new_id:
                        st.caption("Workflow ID")
                        st.code(str(new_id))
                        st.button(
                            "Use this workflow",
                            key=f"use_workflow_{new_id}",
                            on_click=select_created_workflow,
                        )
                        st.caption(
                            "Selecting it fills the sidebar project and "
                            "workflow IDs, avoiding lookup errors."
                        )
                    st.caption(result.get("message", ""))
                except APIError as exc:
                    show_api_error(exc)

        if st.session_state.get("created_workflow_id"):
            st.caption("Latest workflow created in this session.")
            st.button(
                "Use latest workflow",
                key="use_latest_workflow",
                on_click=select_created_workflow,
            )

elif page == "Summary & Submit":
    st.subheader("Summary and Team Lead submission")

    if not project_id or not workflow_id:
        st.info("Enter the project ID and workflow UUID in the sidebar.")
    else:
        try:
            workflow = get_workflow(project_id, workflow_id, access_token) or {}
        except APIError as exc:
            show_api_error(exc)
        else:
            workflow_status = workflow.get("status", "unknown")
            review_status = workflow.get(
                "review_status",
                "pending_human_review" if workflow_status == "completed" else None,
            )
            st.caption(
                f"Workflow: {workflow_status} · "
                f"Review status: {review_status or 'not ready'}"
            )

            result = workflow.get("result") or {}
            draft = result.get("draft") or {}
            if draft:
                st.markdown(f"### {draft.get('title', 'Literature summary')}")
                st.markdown(draft.get("executive_summary", ""))
                if draft.get("key_findings"):
                    st.markdown("#### Key findings")
                    st.json(draft["key_findings"])
                if draft.get("conclusion"):
                    st.markdown("#### Conclusion")
                    st.write(draft["conclusion"])
                st.warning(
                    "This summary is a draft. Human review is required before use."
                )
            elif workflow_status != "completed":
                st.error(
                    workflow.get("error_message")
                    or "The workflow has not produced a summary."
                )

            if workflow_status == "completed":
                if workflow.get("current_stage") == "submitted_to_team_lead":
                    st.success("Submitted to the Team Lead review queue.")
                elif review_status == "approved":
                    st.success("Approved by the Team Lead.")
                    st.info(
                        "Use the PDF Download or Word Download navigation "
                        "option to export the approved summary."
                    )
                elif st.button("Submit to Team Lead", type="primary"):
                    try:
                        submitted = submit_for_review(
                            project_id,
                            workflow_id,
                            access_token,
                        )
                        message = (
                            submitted.get("message")
                            if isinstance(submitted, dict)
                            else None
                        )
                        st.success(message or "Submitted to the Team Lead.")
                        st.rerun()
                    except APIError as exc:
                        show_api_error(exc)

elif page == "Team Lead Queue":
    st.subheader("Team Lead review queue")
    try:
        queue_data = get_review_queue(access_token)
    except APIError as exc:
        show_api_error(exc)
    else:
        items = queue_data.get("items", [])
        if not items:
            st.info("There are no summaries waiting for Team Lead review.")
        else:
            for item in items:
                with st.container(border=True):
                    st.markdown(
                        f"**{item['project_name']}** · "
                        f"Project {item['project_id']}"
                    )
                    st.write(item["research_question"])
                    st.caption(
                        f"Submitted: {item['submitted_at']} · "
                        f"Status: {item['review_status']}"
                    )
                    st.code(item["workflow_id"])
                    st.button(
                        "Open this review",
                        key=f"open_review_{item['workflow_id']}",
                        on_click=select_queue_workflow,
                        args=(item,),
                    )
            st.caption(
                "Use the workflow UUID above in the sidebar, then open "
                "Review & Export to approve or request changes."
            )

elif page == "PDF Download":
    render_download_page("pdf")

elif page == "Word Download":
    render_download_page("docx")

elif page == "Review & Export":
    st.subheader("Review and export")

    if not project_id or not workflow_id:
        st.warning("Enter both project and workflow UUIDs in the sidebar to review a draft.")
    else:
        if st.button("Load current revision"):
            try:
                st.session_state["review_data"] = get_review(
                    project_id,
                    workflow_id,
                    access_token,
                )
            except APIError as exc:
                show_api_error(exc)

        review_data = st.session_state.get("review_data")

        if review_data:
            revision = review_data["current_revision"]
            content = revision["content"]
            revision_id = revision["id"]

            st.caption(
                f"Version {revision['version_number']} · "
                f"Status: {revision['status']}"
            )

            st.warning(
                "Inspect the cited source passages before approval. "
                "AI-generated content should not replace scientific review."
            )

            edited = dict(content)
            edited["title"] = st.text_input(
                "Title",
                value=content.get("title", ""),
                key=f"review_title_{revision_id}",
            )
            edited["executive_summary"] = st.text_area(
                "Executive summary",
                value=content.get("executive_summary", ""),
                height=180,
                key=f"review_summary_{revision_id}",
            )
            edited["conclusion"] = st.text_area(
                "Conclusion",
                value=content.get("conclusion", ""),
                height=120,
                key=f"review_conclusion_{revision_id}",
            )

            with st.expander("Findings, limitations and citations"):
                for field_name, label in (
                    ("key_findings", "Key findings"),
                    ("limitations", "Limitations"),
                    ("evidence_gaps", "Evidence gaps"),
                    ("citations", "Citations"),
                ):
                    edited[field_name] = st.text_area(
                        f"{label} (JSON array)",
                        value=json.dumps(content.get(field_name, []), indent=2),
                        key=f"review_{field_name}_{revision_id}",
                        height=140,
                    )

            comment = st.text_area(
                "Reviewer comments",
                key=f"review_comment_{revision_id}",
            )

            if st.button("Save revised version"):
                try:
                    for field_name in (
                        "key_findings",
                        "limitations",
                        "evidence_gaps",
                        "citations",
                    ):
                        parsed = json.loads(edited[field_name])
                        if not isinstance(parsed, list):
                            raise ValueError(
                                f"{field_name.replace('_', ' ').title()} "
                                "must be a JSON array."
                            )
                        edited[field_name] = parsed
                except (json.JSONDecodeError, ValueError) as exc:
                    st.error(f"Could not save revision: {exc}")
                else:
                    try:
                        result = save_review(
                            project_id,
                            workflow_id,
                            edited,
                            access_token,
                            comment or "Draft edited; review required again.",
                        )
                        st.session_state.pop("review_data", None)
                        st.success("New revision saved. Reload to review it.")
                        st.json(result)
                    except APIError as exc:
                        show_api_error(exc)

            col1, col2 = st.columns(2)
            with col1:
                if st.button("Approve current version"):
                    try:
                        result = record_decision(
                            project_id,
                            workflow_id,
                            "approved",
                            comment,
                            access_token,
                        )
                        st.session_state.pop("review_data", None)
                        st.success("Approval recorded.")
                        st.json(result)
                    except APIError as exc:
                        show_api_error(exc)

            with col2:
                if st.button("Reject current version"):
                    try:
                        result = record_decision(
                            project_id,
                            workflow_id,
                            "rejected",
                            comment,
                            access_token,
                        )
                        st.session_state.pop("review_data", None)
                        st.warning("Rejection recorded.")
                        st.json(result)
                    except APIError as exc:
                        show_api_error(exc)
