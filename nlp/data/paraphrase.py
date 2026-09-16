"""
Paraphrase template rows into natural phrasing, keeping the labels fixed.

The template generator gives you coverage; this gives you surface variety, which
is what actually makes the transformer generalize to real users. Labels are NOT
re-predicted — they're carried over, because the paraphrase is constrained to
preserve meaning. Anything the model gets wrong gets caught in review.py.

Usage:
    export ANTHROPIC_API_KEY=...
    pip install anthropic
    python paraphrase.py --in data/train.csv --out data/paraphrased.csv --per-row 2
"""

import argparse
import csv
import json
import os
import sys

import anthropic

MODEL = "claude-sonnet-4-6"

SYSTEM = """You rewrite short HVAC complaint messages as a real building occupant \
would type them on a phone.

Rules:
- Preserve the exact meaning: same room, same parameter (temperature/humidity/airflow), \
same desired direction, same severity. Do not make a mild complaint sound severe.
- If the original does NOT name a room, the paraphrase must NOT name one either.
- Keep it to one short sentence. Casual, lowercase, contractions fine, occasional typo fine.
- Vary sentence structure, not just synonyms.

Return ONLY a JSON array of strings. No preamble, no markdown fences."""


def paraphrase_batch(client, rows, per_row):
    payload = [
        {"text": r["text"], "room_named": r["zone_id"] != "UNSPECIFIED",
         "parameter": r["parameter"], "wants": r["direction"], "severity": r["intensity"]}
        for r in rows
    ]
    prompt = (
        f"Give exactly {per_row} paraphrase(s) for EACH message below.\n"
        f"Return a flat JSON array of {len(rows) * per_row} strings, in order "
        f"({per_row} for message 1, then {per_row} for message 2, and so on).\n\n"
        f"{json.dumps(payload, indent=1)}"
    )
    resp = client.messages.create(
        model=MODEL, max_tokens=4000, system=SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = "".join(b.text for b in resp.content if b.type == "text")
    raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    out = json.loads(raw)
    if len(out) != len(rows) * per_row:
        raise ValueError(f"expected {len(rows) * per_row} paraphrases, got {len(out)}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="data/val.csv",
                    help="source rows to paraphrase — use val.csv/test.csv, NOT "
                         "train.csv, so paraphrases stay on the held-out side "
                         "of the split (see generate_data.py's build_vocab_pools)")
    ap.add_argument("--out", dest="out", default="data/paraphrased.csv")
    ap.add_argument("--per-row", type=int, default=2)
    ap.add_argument("--batch", type=int, default=15)
    ap.add_argument("--limit", type=int, default=None, help="cap input rows (for a cheap test run)")
    args = ap.parse_args()

    if args.inp.endswith("train.csv"):
        print("warning: paraphrasing train.csv will make val/test look "
              "artificially easy (they'd share phrasing DNA with train). "
              "Paraphrase val.csv/test.csv instead unless you specifically "
              "want more train coverage.", file=sys.stderr)

    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("set ANTHROPIC_API_KEY first")

    with open(args.inp, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if args.limit:
        rows = rows[: args.limit]

    client = anthropic.Anthropic()
    cols = ["text", "zone_id", "parameter", "direction", "intensity", "source",
            "parent_text", "reviewed"]
    written = 0
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for i in range(0, len(rows), args.batch):
            chunk = rows[i : i + args.batch]
            try:
                paras = paraphrase_batch(client, chunk, args.per_row)
            except Exception as e:
                print(f"  batch {i // args.batch} failed ({e}) — skipping", file=sys.stderr)
                continue
            for j, r in enumerate(chunk):
                for p in paras[j * args.per_row : (j + 1) * args.per_row]:
                    w.writerow({"text": p.strip(), "zone_id": r["zone_id"],
                                "parameter": r["parameter"], "direction": r["direction"],
                                "intensity": r["intensity"], "source": "llm_paraphrase",
                                "parent_text": r["text"], "reviewed": 0})
                    written += 1
            print(f"  {min(i + args.batch, len(rows))}/{len(rows)} rows -> {written} paraphrases")

    print(f"\nwrote {written} rows to {args.out}")
    print("Next: python -m streamlit run review.py  (spot-check ~15% before training)")


if __name__ == "__main__":
    main()
