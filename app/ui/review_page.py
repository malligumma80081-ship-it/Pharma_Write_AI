
import json
import os

import requests
import streamlit as st

API_BASE_URL = os.getenv(
    "PHARMAWRITE_API_URL",
    "http://localhost:8000",
).rstrip("/")


def _api_error_detail(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text or f"HTTP {response.status_code}"

    detail = payload.get("detail") if isinstance(payload, dict) else None
    if isinstance(detail, str):
        return detail
    return str(detail) if detail is not None else f"HTTP {response.status_code}"


def _parse_json_list(value: str, field_name: str) -> list:
    parsed = json.loads(value)
    if not isinstance(parsed, list):
        raise ValueError(f"{field_name} must be a JSON array.")
    return parsed


st.title("PharmaWrite AI — Draft Review")

project_id = st.text_input("Project ID (integer)")
workflow_id = st.text_input("Workflow UUID")

if st.button("Load draft"):
    st.session_state.pop("review_data", None)
    if not project_id.strip() or not workflow_id.strip():
        st.error("Enter the numeric project ID and workflow UUID.")
    else:
        try:
            numeric_project_id = int(project_id.strip())
            if numeric_project_id < 1:
                raise ValueError("Project ID must be positive.")
            response = requests.get(
                f"{API_BASE_URL}/api/v1/projects/{numeric_project_id}/"
                f"workflows/{workflow_id.strip()}/review",
                timeout=30,
            )
            if response.status_code == 409:
                st.error(
                    "This workflow is not ready for draft review: "
                    f"{_api_error_detail(response)}"
                )
                try:
                    status_response = requests.get(
                        f"{API_BASE_URL}/api/v1/projects/{numeric_project_id}/"
                        f"workflows/{workflow_id.strip()}",
                        timeout=30,
                    )
                    status_response.raise_for_status()
                    workflow = status_response.json()
                    st.info(
                        "Workflow status: "
                        f"{workflow.get('status', 'unknown')} — "
                        f"{workflow.get('current_stage', 'unknown')}. "
                        "Load the draft again after the workflow completes."
                    )
                    if workflow.get("error_message"):
                        st.error(
                            f"Workflow error: {workflow['error_message']}"
                        )
                except requests.RequestException as status_error:
                    st.info(
                        "Could not retrieve workflow status: "
                        f"{status_error}"
                    )
                st.stop()
            response.raise_for_status()
            st.session_state["review_data"] = response.json()
            st.session_state["review_project_id"] = numeric_project_id
            st.session_state["review_workflow_id"] = workflow_id.strip()
        except ValueError:
            st.error("Project ID must be a positive integer.")
        except requests.HTTPError as exc:
            error_response = exc.response
            if error_response is not None:
                st.error(
                    f"Could not load draft "
                    f"({error_response.status_code}): "
                    f"{_api_error_detail(error_response)}"
                )
            else:
                st.error(f"Could not load draft: {exc}")
        except requests.RequestException as exc:
            st.error(
                "Could not connect to the API while loading the draft: "
                f"{exc}"
            )


review_data = st.session_state.get("review_data")

if review_data:
    revision = review_data["current_revision"]
    content = revision["content"]

    st.caption(
        f"Version {revision['version_number']} · "
        f"Status: {revision['status']}"
    )

    st.warning(
        "AI-generated scientific content requires qualified "
        "human review before use."
    )

    edited_content = dict(content)
    edited_content["title"] = st.text_input(
        "Draft title",
        value=content.get("title", ""),
    )

    edited_content["executive_summary"] = st.text_area(
        "Executive summary",
        value=content.get("executive_summary", ""),
        height=250,
    )

    edited_content["key_findings"] = st.text_area(
        "Key findings (JSON array)",
        value=json.dumps(content.get("key_findings", []), indent=2),
        height=180,
    )
    edited_content["limitations"] = st.text_area(
        "Limitations (JSON array)",
        value=json.dumps(content.get("limitations", []), indent=2),
        height=140,
    )
    edited_content["citations"] = st.text_area(
        "Citations (JSON array)",
        value=json.dumps(content.get("citations", []), indent=2),
        height=180,
    )

    comment = st.text_area("Reviewer comments")

    if st.button("Save revised draft"):
        try:
            edited_content["key_findings"] = _parse_json_list(
                edited_content["key_findings"],
                "Key findings",
            )
            edited_content["limitations"] = _parse_json_list(
                edited_content["limitations"],
                "Limitations",
            )
            edited_content["citations"] = _parse_json_list(
                edited_content["citations"],
                "Citations",
            )
        except ValueError as exc:
            st.error(f"Could not save draft: {exc}")
        else:
            project_id = st.session_state["review_project_id"]
            workflow_id = st.session_state["review_workflow_id"]
            try:
                response = requests.put(
                    f"{API_BASE_URL}/api/v1/projects/{project_id}/"
                    f"workflows/{workflow_id}/review",
                    json={
                        "content": edited_content,
                        "comment": comment
                        or "Draft edited; review required again.",
                    },
                    timeout=30,
                )
                response.raise_for_status()
                st.session_state.pop("review_data", None)
                st.success("New revision saved. Reload the draft to review it.")
            except requests.RequestException as exc:
                st.error(f"Could not save revision: {exc}")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Approve draft"):
            project_id = st.session_state["review_project_id"]
            workflow_id = st.session_state["review_workflow_id"]
            try:
                response = requests.post(
                    f"{API_BASE_URL}/api/v1/projects/{project_id}/"
                    f"workflows/{workflow_id}/review/decision",
                    json={
                        "decision": "approved",
                        "comment": comment,
                    },
                    timeout=30,
                )
                response.raise_for_status()
                st.session_state.pop("review_data", None)
                st.success("Approval recorded. Reload to see the new status.")
            except requests.RequestException as exc:
                st.error(f"Could not record approval: {exc}")

    with col2:
        if st.button("Reject draft"):
            project_id = st.session_state["review_project_id"]
            workflow_id = st.session_state["review_workflow_id"]
            try:
                response = requests.post(
                    f"{API_BASE_URL}/api/v1/projects/{project_id}/"
                    f"workflows/{workflow_id}/review/decision",
                    json={
                        "decision": "rejected",
                        "comment": comment,
                    },
                    timeout=30,
                )
                response.raise_for_status()
                st.session_state.pop("review_data", None)
                st.warning("Rejection recorded. Reload to see the new status.")
            except requests.RequestException as exc:
                st.error(f"Could not record rejection: {exc}")

    st.caption(
        "Demo UI: add authentication, role-based permissions, "
        "and source-level evidence navigation "
        "before customer deployment."
    )


import requests
import streamlit as st

# Assumes project_id and workflow_id have already been entered
# and validated by your existing review screen.

base = (
    f"{API_BASE_URL}/api/v1/projects/{project_id}"
    f"/workflows/{workflow_id}/export"
)

st.subheader("Download your document")

for file_format, label, mime in [
    ("pdf", "Download PDF", "application/pdf"),
    (
        "docx",
        "Download Word document",
        "application/vnd.openxmlformats-officedocument."
        "wordprocessingml.document",
    ),
]:
    try:
        response = requests.get(
            base,
            params={"format": file_format},
            timeout=60,
        )
        response.raise_for_status()

        st.download_button(
            label=label,
            data=response.content,
            file_name=f"pharmawrite_review_v1.{file_format}",
            mime=mime,
            key=f"download_{file_format}",
        )
    except requests.RequestException:
        st.error(
            f"Unable to prepare the {file_format.upper()} export. "
            "Check the workflow and try again."
        )

