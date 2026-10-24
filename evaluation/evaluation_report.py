import argparse
import json
from pathlib import Path


def count_cases(dataset_path: Path) -> int:
    with dataset_path.open(encoding="utf-8") as dataset:
        return sum(1 for line in dataset if line.strip() and json.loads(line))


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate an evaluation dataset.")
    parser.add_argument(
        "dataset",
        nargs="?",
        type=Path,
        default=Path(__file__).with_name("golden_dataset.jsonl"),
    )
    args = parser.parse_args()
    print(f"Validated {count_cases(args.dataset)} evaluation cases.")


if __name__ == "__main__":
    main()
