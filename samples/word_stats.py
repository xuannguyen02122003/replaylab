"""Word statistics for a text file (an ordinary script, no ReplayLab code).

    python word_stats.py some_file.txt
"""

import re
import sys
from collections import Counter
from pathlib import Path


def read_words(path: Path) -> list[str]:
    return re.findall(r"[a-zA-Z']+", path.read_text(encoding="utf-8").lower())


def average_length(words: list[str]) -> float:
    return sum(len(w) for w in words) / len(words)  # empty file -> ZeroDivisionError


def top_words(words: list[str], n: int = 5) -> list[tuple[str, int]]:
    return Counter(words).most_common(n)


def main() -> None:
    words = read_words(Path(sys.argv[1]))
    print(f"words: {len(words)}")
    print(f"average length: {average_length(words):.2f}")
    for word, count in top_words(words):
        print(f"  {word:<12} {count}")


if __name__ == "__main__":
    main()
