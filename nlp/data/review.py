"""
Label / review tool for the 4-head HVAC slot dataset.

Two jobs, same UI:
  1. Review LLM paraphrases (labels pre-filled, you confirm or correct).
  2. Label raw production messages from scratch (labels blank).

Keyboard-light and fast: one message at a time, 4 dropdowns, Enter-free.
Saves after every decision, so you can quit mid-way and resume.

Usage:
    pip install streamlit pandas
    python -m streamlit run review.py -- --file data/paraphrased.csv
"""

import argparse
import os
import sys

import pandas as pd
import streamlit as st

UNSPEC = "UNSPECIFIED"
CHOICES = {
    "zone_id": [UNSPEC, "zone_living", "zone_bedroom", "zone_kitchen",
                "zone_office", "zone_bathroom", "zone_common"],
    "parameter": [UNSPEC, "temperature", "humidity", "airflow"],
    "direction": [UNSPEC, "increase", "decrease"],
    "intensity": [UNSPEC, "mild", "moderate", "strong"],
}
HEADS = list(CHOICES)


def parse_args():
    argv = sys.argv[1:]
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="data/paraphrased.csv")
    known, _ = ap.parse_known_args(argv)
    return known


@st.cache_data
def load(path):
    df = pd.read_csv(path)
    for h in HEADS:
        if h not in df.columns:
            df[h] = UNSPEC
    if "reviewed" not in df.columns:
        df["reviewed"] = 0
    if "keep" not in df.columns:
        df["keep"] = 1
    return df.fillna({h: UNSPEC for h in HEADS})


def main():
    args = parse_args()
    st.set_page_config(page_title="HVAC slot review", layout="centered")
    st.title("HVAC slot review")

    if not os.path.exists(args.file):
        st.error(f"No such file: {args.file}")
        return

    if "df" not in st.session_state:
        st.session_state.df = load(args.file)
    df = st.session_state.df

    todo = df.index[df["reviewed"] == 0].tolist()
    done = len(df) - len(todo)
    st.progress(done / len(df) if len(df) else 1.0,
                text=f"{done} / {len(df)} reviewed")

    if not todo:
        st.success("All reviewed.")
        st.download_button("Download reviewed CSV", df.to_csv(index=False),
                           file_name="reviewed.csv", mime="text/csv")
        st.dataframe(df[df["keep"] == 1][["text"] + HEADS], use_container_width=True)
        return

    i = todo[0]
    row = df.loc[i]

    st.markdown(f"### “{row['text']}”")
    if isinstance(row.get("parent_text"), str) and row.get("parent_text"):
        st.caption(f"paraphrased from: {row['parent_text']}")

    picks = {}
    c1, c2 = st.columns(2)
    for col, heads in ((c1, HEADS[:2]), (c2, HEADS[2:])):
        with col:
            for h in heads:
                cur = row[h] if row[h] in CHOICES[h] else UNSPEC
                picks[h] = st.selectbox(h, CHOICES[h], index=CHOICES[h].index(cur),
                                        key=f"{h}_{i}")

    st.caption("UNSPECIFIED = genuinely not in this message (must come from "
               "conversation context). Don't guess it from the room you imagine.")

    b1, b2, b3 = st.columns([2, 2, 1])
    if b1.button("Confirm / save", type="primary", use_container_width=True):
        for h in HEADS:
            df.at[i, h] = picks[h]
        df.at[i, "reviewed"] = 1
        df.to_csv(args.file, index=False)
        st.rerun()
    if b2.button("Discard (bad paraphrase)", use_container_width=True):
        df.at[i, "reviewed"] = 1
        df.at[i, "keep"] = 0
        df.to_csv(args.file, index=False)
        st.rerun()
    if b3.button("Skip", use_container_width=True):
        st.session_state.df = pd.concat([df.drop(index=i), df.loc[[i]]]).reset_index(drop=True)
        st.rerun()


if __name__ == "__main__":
    main()
