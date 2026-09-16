"""
Synthetic data generator for HVAC complaint slot extraction.

Emits 4 labels per utterance: zone_id, parameter, direction, intensity.
Room phrasings are drawn from zone_vocab.json (real user phrasings extracted
from the Liu et al. NLU-Evaluation-Data corpus, CC BY 4.0) so the surface forms
are closer to how people actually name rooms than hand-invented ones.

Usage:
    python generate_data.py --n 1200 --out data/
"""

import argparse
import csv
import json
import os
import random
from collections import Counter

UNSPEC = "UNSPECIFIED"

# --- 1. Zone config -----------------------------------------------------------
# canonical zone_id -> surface aliases users actually type.
# Edit this to match the zones your building/app actually has.
ZONES = {
    "zone_living": ["living room", "front room", "lounge", "drawing hall", "sitting room",
                    "den", "game room", "playroom", "media room"],
    "zone_bedroom": ["bedroom", "bed room", "master bedroom", "my room", "guest room",
                     "kids bedroom", "my son's room", "bed room two"],
    "zone_kitchen": ["kitchen", "galley"],
    "zone_office": ["office", "study", "work room", "study room"],
    "zone_bathroom": ["bathroom", "washroom", "bath", "bathrooms"],
    "zone_common": ["hall", "hallway", "lobby", "corridor", "dining room", "dining area",
                    "mud room"],
}
# NOTE: "media room" moved from zone_office to zone_living below — it's an
# entertainment room in the source vocabulary, not a workspace. zone_kitchen
# stays thin (2 aliases) because English genuinely has few common synonyms
# for "kitchen" — that's a real ceiling, not a data-collection gap.

# --- 2. Complaint phrasings ---------------------------------------------------
# (parameter, direction) -> list of core phrases, each with its own intensity tier.
# direction = the change the user WANTS, not the state they report.
#   "too cold"  -> direction=increase (raise the temperature)
#   "too humid" -> direction=decrease (lower the humidity)
CORE = {
    ("temperature", "increase"): {
        "mild": ["a bit chilly", "slightly cool", "a little cold", "a touch cold"],
        "moderate": ["cold", "too cold", "quite cold", "colder than I'd like"],
        "strong": ["freezing", "way too cold", "absolutely freezing", "unbearably cold",
                   "like an icebox"],
    },
    ("temperature", "decrease"): {
        "mild": ["a bit warm", "slightly warm", "a little too warm", "a touch stuffy and warm"],
        "moderate": ["hot", "too hot", "quite hot", "warmer than I'd like"],
        "strong": ["boiling", "way too hot", "sweltering", "unbearably hot", "like an oven"],
    },
    ("humidity", "increase"): {
        "mild": ["a bit dry", "slightly dry"],
        "moderate": ["dry", "too dry", "really dry"],
        "strong": ["bone dry", "way too dry", "so dry my throat hurts"],
    },
    ("humidity", "decrease"): {
        "mild": ["a bit humid", "slightly muggy", "a little clammy"],
        "moderate": ["humid", "too humid", "muggy", "sticky"],
        "strong": ["way too humid", "swampy", "unbearably muggy", "dripping with humidity"],
    },
    ("airflow", "increase"): {
        "mild": ["a bit stuffy", "slightly stale"],
        "moderate": ["stuffy", "too stuffy", "airless", "not enough air moving"],
        "strong": ["completely airless", "suffocating", "no air at all in here"],
    },
    ("airflow", "decrease"): {
        "mild": ["a bit drafty", "slightly breezy"],
        "moderate": ["drafty", "too drafty", "windy", "too much air blowing"],
        "strong": ["like a wind tunnel", "blasting air everywhere", "way too drafty"],
    },
}

# --- 3. Sentence frames -------------------------------------------------------
# {core} = complaint phrase, {zone} = room alias (omitted in context-dependent frames)
ZONED_FRAMES = [
    "it's {core} in the {zone}",
    "it is {core} in the {zone}",
    "the {zone} is {core}",
    "{zone} is {core}",
    "it's been {core} in the {zone} all day",
    "can you do something about the {zone}, it's {core}",
    "{core} in the {zone} again",
    "why is the {zone} so {core}",
    "the {zone} feels {core}",
    "please fix the {zone}, it's {core}",
    "we're sitting in the {zone} and it's {core}",
]

# Context-dependent: zone must come from ConversationManager state, not the text.
CONTEXTUAL_FRAMES = [
    "it's {core}",
    "it is {core} now",
    "still {core}",
    "it's {core} in here",
    "getting {core}",
    "now it's {core}",
    "{core} again",
    "it's {core} again in here",
    "honestly it's just {core}",
]

# Follow-ups where parameter/direction also come from context.
PARAM_CONTEXTUAL = [
    ("a bit more please", "mild"),
    ("more", "moderate"),
    ("a lot more", "strong"),
    ("still not enough", "moderate"),
    ("way more than that", "strong"),
    ("just a touch", "mild"),
]

TYPOS = {"the": "teh", "it's": "its", "really": "realy", "freezing": "freezin",
         "bedroom": "bedrom", "kitchen": "kitchn", "humid": "humind"}


def inject_typo(text, rng, rate=0.12):
    if rng.random() > rate:
        return text
    words = text.split()
    for i, w in enumerate(words):
        if w in TYPOS and rng.random() < 0.5:
            words[i] = TYPOS[w]
            break
    return " ".join(words)


def _holdout_split(items, frac, rng):
    """Partition a list of surface forms into (train_pool, heldout_pool).
    Heldout items never appear in any train row, only in val/test."""
    items = list(items)
    rng.shuffle(items)
    n_heldout = max(1, round(len(items) * frac)) if len(items) > 1 else 0
    return items[n_heldout:], items[:n_heldout]


def build_vocab_pools(seed, holdout_frac=0.25):
    """Split every surface-form vocabulary (frames, core phrases, zone aliases)
    into a train pool and a held-out pool BEFORE any rows are generated.

    This is the actual fix for the train/val leakage from the first pass: that
    version split ROWS after generation, so val got sentences built from the
    exact same frames and phrases train saw ("kitchen is hot" vs "the kitchen is
    hot" — different rows, same template). A model doesn't have to generalize to
    score well on that; it has to memorize the template.

    Held-out pools are reserved for val/test only, so val/test measure whether
    the model handles sentence structures and word choices it never trained on
    — which is the thing you actually care about before shipping.
    """
    rng = random.Random(seed)
    pools = {"zoned_frames": {}, "contextual_frames": {}, "core": {}, "zone_alias": {}}
    pools["zoned_frames"]["train"], pools["zoned_frames"]["holdout"] = _holdout_split(
        ZONED_FRAMES, holdout_frac, rng)
    pools["contextual_frames"]["train"], pools["contextual_frames"]["holdout"] = _holdout_split(
        CONTEXTUAL_FRAMES, holdout_frac, rng)
    pools["core"]["train"], pools["core"]["holdout"] = {}, {}
    for key, tiers in CORE.items():
        pools["core"]["train"][key], pools["core"]["holdout"][key] = {}, {}
        for tier, phrases in tiers.items():
            tr, ho = _holdout_split(phrases, holdout_frac, rng)
            # guarantee at least one phrase on each side even for short lists
            if not tr:
                tr = [ho.pop()]
            pools["core"]["train"][key][tier] = tr
            pools["core"]["holdout"][key][tier] = ho or tr[-1:]
    pools["zone_alias"]["train"], pools["zone_alias"]["holdout"] = {}, {}
    for zone, aliases in ZONES.items():
        tr, ho = _holdout_split(aliases, holdout_frac, rng)
        if not tr:
            tr = [ho.pop()]
        pools["zone_alias"]["train"][zone] = tr
        pools["zone_alias"]["holdout"][zone] = ho or tr[-1:]
    return pools


def _generate_from_pool(n, pool, contextual_frac, param_context_frac, typo_rate,
                        rng, source_tag):
    rows, seen = [], set()
    attempts = 0
    zoned_frames = pool["zoned_frames"]
    contextual_frames = pool["contextual_frames"]
    while len(rows) < n and attempts < max(n * 80, 2000):
        attempts += 1
        r = rng.random()

        if r < param_context_frac:
            text, intensity = rng.choice(PARAM_CONTEXTUAL)
            zone, param, direction = UNSPEC, UNSPEC, UNSPEC
        else:
            (param, direction), tiers = rng.choice(list(pool["core"].items()))
            intensity = rng.choice(["mild", "moderate", "strong"])
            core = rng.choice(tiers[intensity])
            if r < param_context_frac + contextual_frac:
                text = rng.choice(contextual_frames).format(core=core)
                zone = UNSPEC
            else:
                zone = rng.choice(list(pool["zone_alias"]))
                alias = rng.choice(pool["zone_alias"][zone])
                text = rng.choice(zoned_frames).format(core=core, zone=alias)

        text = inject_typo(text, rng, typo_rate)
        key = (text, zone, param, direction, intensity)
        if key in seen:
            continue
        seen.add(key)
        rows.append({"text": text, "zone_id": zone, "parameter": param,
                     "direction": direction, "intensity": intensity,
                     "source": source_tag})
    return rows


def generate_split(n_train, n_val, n_test, seed=13, holdout_frac=0.25,
                   contextual_frac=0.30, param_context_frac=0.05, typo_rate=0.12):
    """Generate train from the train-pool vocab and val/test from the held-out
    vocab, so no frame/phrase/alias appears in both. Returns (train, val, test).
    """
    rng = random.Random(seed)
    pools = build_vocab_pools(seed, holdout_frac)

    train_pool = {"zoned_frames": pools["zoned_frames"]["train"],
                 "contextual_frames": pools["contextual_frames"]["train"],
                 "core": pools["core"]["train"],
                 "zone_alias": pools["zone_alias"]["train"]}
    eval_pool = {"zoned_frames": pools["zoned_frames"]["holdout"],
                "contextual_frames": pools["contextual_frames"]["holdout"],
                "core": pools["core"]["holdout"],
                "zone_alias": pools["zone_alias"]["holdout"]}

    train = _generate_from_pool(n_train, train_pool, contextual_frac,
                                param_context_frac, typo_rate, rng, "template_train")
    # val and test draw from the SAME held-out pool but with different seeds/attempts
    # so their sentences differ from each other too, not just from train.
    rng_val = random.Random(seed + 1)
    rng_test = random.Random(seed + 2)
    val = _generate_from_pool(n_val, eval_pool, contextual_frac,
                              param_context_frac, typo_rate, rng_val, "template_heldout")
    test = _generate_from_pool(n_test, eval_pool, contextual_frac,
                               param_context_frac, typo_rate, rng_test, "template_heldout")
    # de-dup val/test against each other and against train, by exact text
    seen_text = {r["text"] for r in train}
    val = [r for r in val if r["text"] not in seen_text and not seen_text.add(r["text"])]
    test = [r for r in test if r["text"] not in seen_text and not seen_text.add(r["text"])]
    return train, val, test


def write_csv(path, rows):
    cols = ["text", "zone_id", "parameter", "direction", "intensity", "source"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-train", type=int, default=1000)
    ap.add_argument("--n-val", type=int, default=150)
    ap.add_argument("--n-test", type=int, default=150)
    ap.add_argument("--holdout-frac", type=float, default=0.25,
                    help="fraction of each frame/phrase/alias vocab reserved "
                         "exclusively for val+test")
    ap.add_argument("--out", default="data")
    ap.add_argument("--seed", type=int, default=13)
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    train, val, test = generate_split(args.n_train, args.n_val, args.n_test,
                                      seed=args.seed, holdout_frac=args.holdout_frac)

    write_csv(os.path.join(args.out, "train.csv"), train)
    write_csv(os.path.join(args.out, "val.csv"), val)
    write_csv(os.path.join(args.out, "test.csv"), test)
    write_csv(os.path.join(args.out, "all.csv"), train + val + test)

    print(f"train {len(train)} / val {len(val)} / test {len(test)} -> {args.out}/")
    print("(val/test use frames, phrases and zone aliases NEVER seen in train — "
          "see build_vocab_pools docstring)\n")
    for name, rows in (("train", train), ("val", val), ("test", test)):
        print(f"[{name}]")
        for head in ["zone_id", "parameter", "direction", "intensity"]:
            c = Counter(r[head] for r in rows)
            print(f"  {head:10s} {dict(c.most_common())}")


if __name__ == "__main__":
    main()
