"""
Phase 4 core model: one shared DistilBERT encoder -> 4 independent linear heads.

Design notes that matter:
  * One encoder, four heads. The heads share language understanding but predict
    independently, so "too cold in the kitchen" trains zone_id, parameter,
    direction and intensity from the same forward pass.
  * Loss = sum of the four weighted cross-entropies. Each head's weights are
    inverse class frequency from the TRAIN split only.
  * Encoder frozen for epoch 1 (heads are randomly initialised; letting their
    large gradients into the encoder early wrecks the pretrained weights on a
    small dataset), then unfrozen.
  * Separate param groups: encoder at 2e-5, heads at 1e-3. Heads are training
    from scratch and need a much larger step.
  * Early stopping on joint exact match, not on loss. Loss can improve while the
    joint number gets worse.

Usage:
    pip install torch transformers safetensors scikit-learn pandas
    python model_multihead.py --data data/ --out artifacts/distilbert
    python model_multihead.py --data data/ --out artifacts/distilbert --test   # Phase 5, once
"""

import argparse
import json
import os

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from safetensors.torch import load_file, save_file
from sklearn.metrics import classification_report, f1_score
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModel, AutoTokenizer

HEADS = [ "parameter", "direction", "intensity"]


# --- data ---------------------------------------------------------------------
class SlotDataset(Dataset):
    def __init__(self, df, tokenizer, label_maps, max_length=64):
        self.enc = tokenizer(
            df["text"].tolist(), max_length=max_length,
            padding="max_length", truncation=True, return_tensors="pt",
        )
        self.labels = {
            h: torch.tensor([label_maps[h][v] for v in df[h]], dtype=torch.long)
            for h in HEADS
        }

    def __len__(self):
        return self.enc["input_ids"].size(0)

    def __getitem__(self, i):
        item = {k: v[i] for k, v in self.enc.items()}
        item["labels"] = {h: self.labels[h][i] for h in HEADS}
        return item


def collate(batch):
    out = {k: torch.stack([b[k] for b in batch]) for k in ("input_ids", "attention_mask")}
    out["labels"] = {h: torch.stack([b["labels"][h] for b in batch]) for h in HEADS}
    return out


def build_label_maps(train_df):
    maps, inv = {}, {}
    for h in HEADS:
        classes = sorted(train_df[h].astype(str).unique())
        maps[h] = {c: i for i, c in enumerate(classes)}
        inv[h] = classes
    return maps, inv


def class_weights(train_df, label_maps, device, power=0.5, max_ratio=10.0):
    """Dampened inverse class frequency, normalised to mean 1.

    Raw inverse frequency (power=1.0) is dangerous here. If UNSPECIFIED is 0.5%
    of the `parameter` column, it gets ~100x the weight of temperature, and the
    model spends its capacity on a handful of rows while the classes that matter
    go unlearned. power=0.5 (sqrt-inverse) plus a hard cap on the max/min ratio
    keeps rare classes represented without letting them dominate.

    If a class needs more than a 10x correction, the real fix is more examples of
    it in the generator, not a bigger weight.
    """
    weights = {}
    for h in HEADS:
        counts = np.zeros(len(label_maps[h]), dtype=np.float64)
        for v in train_df[h].astype(str):
            counts[label_maps[h][v]] += 1
        counts = np.maximum(counts, 1.0)
        w = (counts.sum() / counts) ** power
        w = np.clip(w, w.min(), w.min() * max_ratio)
        w = w / w.mean()
        weights[h] = torch.tensor(w, dtype=torch.float, device=device)
    return weights


# --- model --------------------------------------------------------------------
class MultiHeadSlotModel(nn.Module):
    def __init__(self, backbone="distilbert-base-uncased", n_classes=None, dropout=0.1):
        super().__init__()
        self.encoder = AutoModel.from_pretrained(backbone)
        hidden = self.encoder.config.hidden_size
        self.dropout = nn.Dropout(dropout)
        self.heads = nn.ModuleDict(
            {h: nn.Linear(hidden, n_classes[h]) for h in HEADS}
        )

    def forward(self, input_ids, attention_mask):
        out = self.encoder(input_ids=input_ids, attention_mask=attention_mask)
        # DistilBERT has no pooler; take the [CLS] token from the last layer.
        pooled = self.dropout(out.last_hidden_state[:, 0])
        return {h: self.heads[h](pooled) for h in HEADS}

    def set_encoder_trainable(self, flag: bool):
        for p in self.encoder.parameters():
            p.requires_grad = flag


# --- eval ---------------------------------------------------------------------
@torch.no_grad()
def evaluate(model, loader, device, inv_maps, verbose=False):
    model.eval()
    true = {h: [] for h in HEADS}
    pred = {h: [] for h in HEADS}
    for batch in loader:
        logits = model(batch["input_ids"].to(device), batch["attention_mask"].to(device))
        for h in HEADS:
            pred[h].append(logits[h].argmax(-1).cpu().numpy())
            true[h].append(batch["labels"][h].numpy())
    true = {h: np.concatenate(v) for h, v in true.items()}
    pred = {h: np.concatenate(v) for h, v in pred.items()}

    per_head = {h: f1_score(true[h], pred[h], average="macro", zero_division=0) for h in HEADS}
    ok = np.ones(len(true[HEADS[0]]), dtype=bool)
    for h in HEADS:
        ok &= true[h] == pred[h]
    joint = float(ok.mean())

    if verbose:
        for h in HEADS:
            names = inv_maps[h]
            print(f"\n=== {h} (macro F1 {per_head[h]:.3f}) ===")
            print(classification_report(
                [names[i] for i in true[h]], [names[i] for i in pred[h]],
                zero_division=0, digits=3))
    return per_head, joint


# --- train --------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--out", default="artifacts/distilbert")
    ap.add_argument("--backbone", default="distilbert-base-uncased")
    ap.add_argument("--epochs", type=int, default=12)
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--encoder-lr", type=float, default=2e-5)
    ap.add_argument("--head-lr", type=float, default=1e-3)
    ap.add_argument("--weight-decay", type=float, default=0.01)
    ap.add_argument("--dropout", type=float, default=0.1)
    ap.add_argument("--max-length", type=int, default=64)
    ap.add_argument("--patience", type=int, default=3)
    ap.add_argument("--freeze-epochs", type=int, default=1)
    ap.add_argument("--seed", type=int, default=13)
    ap.add_argument("--test", action="store_true",
                    help="load the saved checkpoint and score test.csv once")
    args = ap.parse_args()

    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    os.makedirs(args.out, exist_ok=True)

    def load(name):
        df = pd.read_csv(os.path.join(args.data, f"{name}.csv"))
        if "keep" in df.columns:
            df = df[df["keep"] == 1]
        return df.reset_index(drop=True).astype({h: str for h in HEADS})

    train_df = load("train")
    label_maps, inv_maps = build_label_maps(train_df)
    tokenizer = AutoTokenizer.from_pretrained(args.backbone)
    n_classes = {h: len(label_maps[h]) for h in HEADS}
    model = MultiHeadSlotModel(args.backbone, n_classes, args.dropout).to(device)

    # ---- test-only path: load checkpoint, score once, stop.
    if args.test:
        model.load_state_dict(load_file(os.path.join(args.out, "model.safetensors")))
        test_loader = DataLoader(SlotDataset(load("test"), tokenizer, label_maps,
                                            args.max_length),
                                 batch_size=args.batch_size, collate_fn=collate)
        per_head, joint = evaluate(model, test_loader, device, inv_maps, verbose=True)
        print(f"\nTEST joint exact match: {joint:.3f}")
        with open(os.path.join(args.out, "metrics_test.json"), "w") as f:
            json.dump({**{k: round(v, 4) for k, v in per_head.items()},
                       "joint_exact_match": round(joint, 4)}, f, indent=2)
        print("Do not retune after seeing this number.")
        return

    val_df = load("val")
    train_loader = DataLoader(SlotDataset(train_df, tokenizer, label_maps, args.max_length),
                              batch_size=args.batch_size, shuffle=True, collate_fn=collate)
    val_loader = DataLoader(SlotDataset(val_df, tokenizer, label_maps, args.max_length),
                            batch_size=args.batch_size, collate_fn=collate)

    weights = class_weights(train_df, label_maps, device)
    losses = {h: nn.CrossEntropyLoss(weight=weights[h]) for h in HEADS}
    optim = torch.optim.AdamW(
        [
            {"params": model.encoder.parameters(), "lr": args.encoder_lr},
            {"params": model.heads.parameters(), "lr": args.head_lr},
        ],
        weight_decay=args.weight_decay,
    )

    print(f"device={device}  train={len(train_df)}  val={len(val_df)}")
    print("classes per head: " + "  ".join(f"{h}={n_classes[h]}" for h in HEADS) + "\n")

    best, bad_epochs = -1.0, 0
    for epoch in range(1, args.epochs + 1):
        frozen = epoch <= args.freeze_epochs
        model.set_encoder_trainable(not frozen)
        model.train()
        head_loss_sum = {h: 0.0 for h in HEADS}
        n_batches = 0

        for batch in train_loader:
            optim.zero_grad()
            logits = model(batch["input_ids"].to(device), batch["attention_mask"].to(device))
            total = 0.0
            for h in HEADS:
                l = losses[h](logits[h], batch["labels"][h].to(device))
                head_loss_sum[h] += l.item()
                total = total + l
            total.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optim.step()
            n_batches += 1

        per_head, joint = evaluate(model, val_loader, device, inv_maps)
        tag = " [encoder frozen]" if frozen else ""
        # Per-head losses logged separately so a single lagging head is visible.
        loss_str = "  ".join(f"{h}={head_loss_sum[h] / n_batches:.3f}" for h in HEADS)
        f1_str = "  ".join(f"{h}={per_head[h]:.3f}" for h in HEADS)
        print(f"epoch {epoch:2d}{tag}\n  loss   {loss_str}\n  val F1 {f1_str}\n"
              f"  val joint exact match {joint:.3f}")

        if joint > best:
            best, bad_epochs = joint, 0
            save_file(model.state_dict(), os.path.join(args.out, "model.safetensors"))
            tokenizer.save_pretrained(args.out)
            with open(os.path.join(args.out, "label_maps.json"), "w") as f:
                json.dump({"label_maps": label_maps, "inv_maps": inv_maps,
                           "backbone": args.backbone, "max_length": args.max_length}, f,
                          indent=2)
            print("  ^ best so far, checkpoint saved")
        else:
            bad_epochs += 1
            if bad_epochs >= args.patience:
                print(f"\nearly stop: no improvement in {args.patience} epochs")
                break

    print(f"\nbest val joint exact match: {best:.3f}  ->  {args.out}/")
    print("Compare against baseline_metrics_val.json before trusting the transformer.")


if __name__ == "__main__":
    main()
