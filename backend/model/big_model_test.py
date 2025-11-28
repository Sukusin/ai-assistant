from collections import Counter
from pathlib import Path
import json

import pandas as pd

from model_logic import process_letter


EXAMPLES_PATH = Path(__file__).with_name("examples.json")


def load_examples(path: str | Path = EXAMPLES_PATH):
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        examples = json.load(f)

    for ex in examples:
        if not all(k in ex for k in ("id", "true_category", "text")):
            raise ValueError(f"Неверный формат примера: {ex}")

    return examples


def analyze_examples(examples=None):
    if examples is None:
        examples = load_examples()

    rows = []

    for ex in examples:
        res = process_letter(ex["text"])
        pred_cat = res["category"]
        info = res.get("info") or {}
        urgency = res.get("urgency")
        priority = None
        if "priority" in res and isinstance(res["priority"], dict):
            priority = res["priority"].get("final_priority")

        row = {
            "id": ex["id"],
            "true_category": ex["true_category"],
            "pred_category": pred_cat,
            "is_correct": ex["true_category"] == pred_cat,
            "urgency": urgency,
            "priority": priority,
            "has_deadline": ("deadline_date" in info) or ("deadline_relative" in info),
            "has_amount": ("amount" in info),
        }
        rows.append(row)

    df = pd.DataFrame(rows)
    return df


if __name__ == "__main__":
    examples = load_examples()

    df = analyze_examples(examples)
    print("=== Детальная таблица ===")
    print(df)

    print("\n=== Общая точность классификации ===")
    acc = df["is_correct"].mean()
    print(f"{acc:.2%}")

    print("\n=== Точность по категориям ===")
    for cat, group in df.groupby("true_category"):
        acc_cat = group["is_correct"].mean()
        print(f"{cat}: {acc_cat:.2%} (n={len(group)})")

    print("\n=== Распределение срочности ===")
    print(df["urgency"].value_counts(dropna=False))

    print("\n=== Распределение приоритета ===")
    print(df["priority"].value_counts(dropna=False).sort_index())

    print("\n=== Доля писем с дедлайном / суммой ===")
    print("has_deadline =", df["has_deadline"].mean())
    print("has_amount   =", df["has_amount"].mean())

    df.to_csv("example_stats.csv", index=False)
