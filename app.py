"""Streamlit UI for the NetScan bill converter.

Upload a legislative bill PDF, confirm the state (auto-detected when possible),
and generate the NetScan amendment markup as a downloadable .txt.

Run:
    pip install -e ".[ui]"
    streamlit run app.py
"""
from __future__ import annotations

import os
import tempfile

import streamlit as st

from netscan.detect import detect_state
from netscan.pipeline import convert
from netscan.profiles import PROFILES

st.set_page_config(page_title="NetScan Bill Converter", layout="wide")
st.title("NetScan Bill Converter")
st.caption(
    "Upload a state legislative bill PDF. The converter reads the PDF geometry "
    "directly (no OCR) and emits amendment markup: deletions as [D>...<D], "
    "additions as [A>...<A]."
)

STATES = sorted(PROFILES)  # e.g. ["CA", "KS"]

uploaded = st.file_uploader("Bill PDF", type=["pdf"])

if uploaded is not None:
    data = uploaded.getvalue()

    # Write once to a temp file: used for detection and conversion.
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as fh:
        fh.write(data)
        tmp_path = fh.name

    try:
        detected = detect_state(tmp_path)
        if detected:
            st.info(f"Detected state: **{detected}**")
            default_index = STATES.index(detected)
        else:
            st.warning("Could not auto-detect the state. Please choose one.")
            default_index = 0

        state = st.selectbox("State profile", STATES, index=default_index)

        if st.button("Convert", type="primary"):
            with st.spinner("Converting..."):
                try:
                    markup = convert(tmp_path, state)
                except Exception as exc:  # surface failures to the user, don't crash
                    st.error(f"Conversion failed: {exc}")
                else:
                    out_name = os.path.splitext(uploaded.name)[0] + ".txt"
                    st.success(f"Generated {len(markup):,} characters.")
                    st.download_button(
                        "Download .txt",
                        data=markup.encode("utf-8"),
                        file_name=out_name,
                        mime="text/plain",
                    )
                    st.text_area("Preview", markup, height=500)
    finally:
        os.unlink(tmp_path)
else:
    st.info("Upload a PDF to begin.")
