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
        create_project,
        download_export,
        get_current_user,
        get_ollama_status,
        get_review,
        get_review_queue,
        ask_knowledge_base,
        index_document,
        list_documents,
        list_projects,
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
        create_project,
        download_export,
        get_current_user,
        get_ollama_status,
        get_review,
        get_review_queue,
        ask_knowledge_base,
        index_document,
        list_documents,
        list_projects,
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
        "selected_project_id",
        "workflow_uuid",
        "workflow_creation_result",
        "pending_workflow_selection",
        "knowledge_answer",
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
        "Projects",
        "Overview",
        "Documents",
        "Knowledge Base",
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
        "Projects",
        "Overview",
        "Documents",
        "Knowledge Base",
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

pending_selection = st.session_state.pop(
    "pending_workflow_selection",
    None,
)
if isinstance(pending_selection, dict):
    st.session_state["project_id"] = pending_selection["project_id"]
    st.session_state["workflow_uuid"] = pending_selection["workflow_id"]

pending_project_id = st.session_state.pop("pending_project_selection", None)
if pending_project_id:
    st.session_state["project_id"] = str(pending_project_id)
    st.session_state["workflow_uuid"] = ""

try:
    projects = list_projects(access_token)
except APIError as exc:
    st.sidebar.error(f"Could not load projects: {exc}")
    projects = []

if not isinstance(projects, list):
    st.sidebar.error("The API returned an invalid project list.")
    projects = []

project_labels = {
    str(project["id"]): f"{project['name']} · ID {project['id']}"
    for project in projects
}
project_options = list(project_labels)
requested_project_id = st.session_state.get("project_id", "")
if requested_project_id not in project_options:
    st.session_state["project_id"] = (
        project_options[0] if project_options else ""
    )
    st.session_state["workflow_uuid"] = ""
    st.session_state.pop("review_data", None)
    st.session_state.pop("approved_export_pdf", None)
    st.session_state.pop("approved_export_docx", None)

previous_project_id = st.session_state.get("selected_project_id")
project_id = st.sidebar.selectbox(
    "Project",
    options=["", *project_options],
    format_func=lambda value: (
        "Select a project" if not value else project_labels[value]
    ),
    key="project_id",
)
if (
    previous_project_id is not None
    and project_id != previous_project_id
    and not isinstance(pending_selection, dict)
):
    st.session_state["workflow_uuid"] = ""
    st.session_state.pop("review_data", None)
    st.session_state.pop("approved_export_pdf", None)
    st.session_state.pop("approved_export_docx", None)
st.session_state["selected_project_id"] = project_id

workflow_id = st.sidebar.text_input("Workflow UUID", key="workflow_uuid").strip()


def show_api_error(exc: APIError):
    message = str(exc)
    if "workflow not found" in message.lower():
        st.error(
            "Workflow not found for this project. Select the project that "
            "owns the workflow and use its exact workflow UUID. Writers can "
            "only open workflows in their own projects; contact an "
            "administrator if this project should belong to your account."
        )
    else:
        st.error(message)


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
    st.session_state["pending_workflow_selection"] = {
        "project_id": str(item["project_id"]),
        "workflow_id": item["workflow_id"],
    }
    st.session_state["navigation"] = "Review & Export"


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


if page == "Projects":
    st.subheader("Your projects")
    if projects:
        st.dataframe(
            [
                {
                    "Project ID": project["id"],
                    "Name": project["name"],
                    "Research question": project["research_question"],
                    "Status": project["status"],
                }
                for project in projects
            ],
            hide_index=True,
            use_container_width=True,
        )
    else:
        st.info("No projects are available. Create a project to get started.")

    if role in ("writer", "admin"):
        st.markdown("### Create a project")
        with st.form("create_project_form"):
            project_name = st.text_input(
                "Project name",
                max_chars=200,
            )
            project_question = st.text_area(
                "Research question",
                max_chars=3000,
                help="Use at least 10 characters.",
            )
            create_project_submitted = st.form_submit_button(
                "Create project",
                type="primary",
            )
        if create_project_submitted:
            try:
                created = create_project(
                    project_name.strip(),
                    project_question.strip(),
                    access_token,
                )
                if not isinstance(created, dict) or "id" not in created:
                    st.error("The API returned an invalid project response.")
                else:
                    st.session_state["pending_project_selection"] = str(
                        created["id"]
                    )
                    st.success(
                        f"Project created: {created['name']} "
                        f"(ID {created['id']})."
                    )
                    st.rerun()
            except APIError as exc:
                show_api_error(exc)

elif page == "Overview":
    st.subheader("Project overview")

    if not project_id:
        st.info("Select a project in the sidebar or create one in Projects.")
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
        st.warning("Select a project in the sidebar before uploading files.")
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
                        if not isinstance(result, dict):
                            st.error(
                                f"{uploaded_file.name}: the API returned an "
                                "invalid upload response."
                            )
                            continue
                        st.success(
                            f"Uploaded and indexed: {uploaded_file.name} "
                            f"({result['indexed_chunks']} passages)."
                        )
                        st.code(result["id"])
                    except APIError as exc:
                        st.error(f"{uploaded_file.name}: {exc}")

        try:
            documents = list_documents(project_id, access_token)
        except APIError as exc:
            show_api_error(exc)
        else:
            if not isinstance(documents, list):
                st.error("The API returned an invalid document list.")
                documents = []
            if documents:
                st.markdown("### Project documents")
                for document in documents:
                    cols = st.columns([4, 2, 1])
                    cols[0].write(document["filename"])
                    cols[1].write(document["status"])
                    if document["status"] != "indexed" and cols[2].button(
                        "Index",
                        key=f"index_{document['id']}",
                    ):
                        try:
                            indexed = index_document(
                                project_id,
                                document["id"],
                                access_token,
                            )
                            if not isinstance(indexed, dict):
                                st.error(
                                    "The API returned an invalid indexing "
                                    "response."
                                )
                                continue
                            st.success(f"{indexed['filename']} is indexed.")
                            st.rerun()
                        except APIError as exc:
                            show_api_error(exc)

elif page == "Knowledge Base":
    st.subheader("Ask your project knowledge base")
    st.caption(
        "Answers use only indexed PDFs and include source-page citations. "
        "If the documents do not support an answer, the assistant will say so."
    )

    if not project_id:
        st.warning("Select a project in the sidebar.")
    else:
        try:
            documents = list_documents(project_id, access_token)
        except APIError as exc:
            show_api_error(exc)
        else:
            if not isinstance(documents, list):
                st.error("The API returned an invalid document list.")
                documents = []
            indexed_documents = [
                document
                for document in documents
                if document["status"] == "indexed"
            ]
            if not indexed_documents:
                st.info(
                    "Upload a PDF from Documents first. It will be added to "
                    "this project's searchable knowledge base."
                )
            else:
                documents_by_id = {
                    document["id"]: document
                    for document in indexed_documents
                }
                selected_ids = st.multiselect(
                    "Search these indexed documents",
                    options=list(documents_by_id),
                    default=list(documents_by_id),
                    format_func=lambda document_id: (
                        f"{documents_by_id[document_id]['filename']} "
                        f"({document_id[:8]})"
                    ),
                )
                question = st.text_area(
                    "Your question",
                    key="knowledge_question_input",
                    placeholder="Ask about the content of your uploaded PDFs.",
                    height=100,
                )
                top_k = st.slider(
                    "Passages to use",
                    min_value=1,
                    max_value=12,
                    value=6,
                    key="knowledge_top_k",
                )
                if st.button("Ask knowledge base", type="primary"):
                    if len(question.strip()) < 3:
                        st.warning(
                            "Enter a question with at least 3 characters."
                        )
                    elif not selected_ids:
                        st.warning("Select at least one indexed document.")
                    else:
                        try:
                            with st.spinner(
                                "Searching documents and preparing an answer..."
                            ):
                                st.session_state.pop("knowledge_answer", None)
                                st.session_state["knowledge_answer"] = (
                                    ask_knowledge_base(
                                        project_id,
                                        question.strip(),
                                        selected_ids,
                                        access_token,
                                        top_k,
                                    )
                                )
                        except APIError as exc:
                            show_api_error(exc)

                answer_result = st.session_state.get("knowledge_answer")
                if (
                    isinstance(answer_result, dict)
                    and answer_result.get("project_id") == project_id
                ):
                    st.markdown("### Answer")
                    st.write(answer_result["answer"])
                    if answer_result["citations"]:
                        st.markdown("### Sources")
                        for citation in answer_result["citations"]:
                            pages = (
                                str(citation["page_start"])
                                if citation["page_start"]
                                == citation["page_end"]
                                else (
                                    f"{citation['page_start']}-"
                                    f"{citation['page_end']}"
                                )
                            )
                            with st.expander(
                                f"{citation['evidence_id']} · "
                                f"{citation['filename']} · page {pages}"
                            ):
                                st.write(citation["quote"])
                    st.caption(
                        "AI-generated answer; verify important claims "
                        "against the cited source pages."
                    )

elif page == "Generate Draft":
    st.subheader("Generate an evidence-grounded draft")

    if not project_id:
        st.warning("Select a project in the sidebar before creating a workflow.")
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
                        st.session_state["pending_workflow_selection"] = {
                            "project_id": str(project_id),
                            "workflow_id": str(new_id),
                        }
                    st.session_state["workflow_creation_result"] = result
                    st.rerun()
                except APIError as exc:
                    show_api_error(exc)

        workflow_result = st.session_state.pop(
            "workflow_creation_result",
            None,
        )
        if workflow_result:
            workflow_id_created = (
                workflow_result.get("workflow_id")
                or workflow_result.get("id")
            )
            if workflow_result.get("status") == "completed":
                st.success(
                    "Workflow completed. Human review is required."
                )
            else:
                st.error(
                    f"Workflow {workflow_result.get('status', 'unknown')} "
                    f"at stage {workflow_result.get('current_stage', 'unknown')}. "
                    f"{workflow_result.get('message', '')}"
                )
                show_ollama_status(st)
            if workflow_id_created:
                st.caption("The sidebar now points to this workflow.")
                st.code(str(workflow_id_created))

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
        if not isinstance(queue_data, dict):
            st.error("The API returned an invalid review queue.")
            st.stop()
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
