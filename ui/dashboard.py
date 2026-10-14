import requests
import streamlit as st

API_URL = "http://localhost:8000"

st.set_page_config(
    page_title="PharmaWrite AI",
    page_icon="🧬",
    layout="wide",
)

st.title("🧬 PharmaWrite AI")
st.caption("Scientific Literature Review & Evidence Summary")

st.info(
    "Prototype: generated content is a draft, not verified "
    "medical evidence. Human review is required."
)

st.subheader("Create a preliminary scientific summary")

source_text = st.text_area(
    "Paste text from an authorized scientific source",
    height=250,
    placeholder=(
        "Paste a short research abstract or study passage here..."
    ),
)

if st.button("Generate Summary", type="primary"):
    if not source_text.strip():
        st.warning("Please enter source text first.")

    else:
        try:
            with st.spinner("Generating preliminary summary..."):
                response = requests.post(
                    f"{API_URL}/api/v1/summary",
                    json={"source_text": source_text},
                    timeout=190,
                )

            if response.status_code == 200:
                result = response.json()

                st.success("Draft generated")
                st.markdown(result["summary"])

                st.warning(
                    "Review the output against the original source. "
                    "Citations and factual claims have not yet been "
                    "independently verified by this prototype."
                )

            else:
                st.error(
                    f"API error ({response.status_code}): "
                    f"{response.text}"
                )

        except requests.RequestException as exc:
            st.error(
                "Cannot connect to the backend. Start FastAPI "
                "and check that it is listening on port 8000."
            )
            st.caption(str(exc))

st.divider()

st.subheader("Day 1 system status")

if st.button("Check Backend Health"):
    try:
        response = requests.get(
            f"{API_URL}/health",
            timeout=5,
        )
        response.raise_for_status()
        st.success(f"Backend status: {response.json()['status']}")

    except requests.RequestException:
        st.error("Backend is not reachable.")