"""Mini MapReduce engine -- pure Python, NO Hadoop or Spark.

The five requested stages are implemented explicitly:
1. Input: each .txt file is a separate split.
2. Map: emit (word, 1) for every occurrence.
3. Parallel map execution: one submitted task per split (ThreadPoolExecutor).
4. Local combine + deterministic partition into EXACTLY 2 reducers.
5. Shuffle, sort, reduce, and save one text file per reducer.
"""

from __future__ import annotations

import re
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path


@dataclass
class FileTrace:
    """Intermediate data for one input file, useful for explaining the phases."""

    filename: str
    pairs: list[tuple[str, int]]
    combined: dict[str, int]


@dataclass
class RunResult:
    """Full result, including intermediate steps for the GUI."""

    traces: list[FileTrace]
    shuffled: list[dict[str, list[int]]]
    reduced: list[dict[str, int]]
    output_paths: list[Path]
    elapsed_seconds: float
    mapper_workers: int

    @property
    def total_words(self) -> int:
        return sum(len(t.pairs) for t in self.traces)

    @property
    def unique_words(self) -> int:
        return len(set().union(*(set(d) for d in self.reduced)))

    @property
    def totals(self) -> dict[str, int]:
        """Only used to DISPLAY the full answer; reducers do the real work."""
        return dict(sorted({word: count for reducer in self.reduced for word, count in reducer.items()}.items()))


def tokenize(text: str) -> list[str]:
    """Lowercase and find letter-only words (supports English and Arabic).

    Punctuation and digits act as separators. For example:
    'Data, DATA! 2026' -> ['data', 'data'].
    """
    return re.findall(r"[^\W\d_]+", text.lower(), flags=re.UNICODE)


def mapper(text: str) -> list[tuple[str, int]]:
    """MAP stage: one (word, 1) for EACH occurrence -- not totals yet."""
    return [(word, 1) for word in tokenize(text)]


def combiner(pairs: list[tuple[str, int]]) -> dict[str, int]:
    """COMBINE stage: count repeated words INSIDE ONE input file."""
    local_counts: dict[str, int] = {}
    for word, value in pairs:
        local_counts[word] = local_counts.get(word, 0) + value
    return local_counts


def map_one_file(path: Path) -> FileTrace:
    """The unit of work submitted to a separate mapper thread."""
    with path.open('r', encoding='utf-8') as handle:
        contents = handle.read()
    pairs = mapper(contents)
    return FileTrace(filename=path.name, pairs=pairs, combined=combiner(pairs))


def partitioner(word: str) -> int:
    """Always send the same word to the same one of TWO reducers."""
    return sum(ord(character) for character in word) % 2


def reducer(values: list[int]) -> int:
    """REDUCE stage: add a word's counts contributed by different files."""
    return sum(values)


def run_mapreduce(
    input_files: list[str | Path],
    output_dir: str | Path = 'output',
    max_workers: int | None = None,
) -> RunResult:
    """Execute the whole small MapReduce pipeline and write 2 outputs.

    Threads run file jobs concurrently. Due to CPython's GIL, threads are
    NOT a guarantee of CPU-parallel execution; they satisfy concurrent
    per-split mapping and work well for this teaching/IO-heavy example.
    """
    if max_workers is not None and max_workers < 1:
        raise ValueError('max_workers must be at least 1')

    paths = sorted((Path(item) for item in input_files), key=lambda p: p.name.lower())
    if not paths:
        raise ValueError('No .txt files found. Add files to the input folder.')
    for path in paths:
        if not path.is_file() or path.suffix.lower() != '.txt':
            raise ValueError(f'Input must be an existing .txt file: {path}')

    start = time.perf_counter()
    workers = len(paths) if max_workers is None else min(max_workers, len(paths))

    # One map_one_file TASK for EACH input split; tasks execute concurrently.
    with ThreadPoolExecutor(max_workers=workers) as executor:
        traces = list(executor.map(map_one_file, paths))

    # PARTITION: map each locally-combined (word, local_count) to reducer 0 or 1.
    partitions: list[defaultdict[str, list[int]]] = [defaultdict(list), defaultdict(list)]
    for trace in traces:
        for word, local_count in trace.combined.items():
            reducer_id = partitioner(word)
            partitions[reducer_id][word].append(local_count)

    # SHUFFLE (group all values of each word) + SORT (alphabetical keys).
    shuffled = [dict(sorted(partition.items())) for partition in partitions]

    # REDUCE: compute final counts independently for each reducer.
    reduced = [
        {word: reducer(values) for word, values in reducer_input.items()}
        for reducer_input in shuffled
    ]

    # One output file PER REDUCER, even when a partition is empty.
    output_folder = Path(output_dir)
    output_folder.mkdir(parents=True, exist_ok=True)
    output_paths = []
    for reducer_id, word_counts in enumerate(reduced):
        output_path = output_folder / f'reducer_{reducer_id}.txt'
        with output_path.open('w', encoding='utf-8') as handle:
            for word, count in word_counts.items():
                handle.write(f'{word}: {count}\n')
        output_paths.append(output_path)

    return RunResult(
        traces=traces,
        shuffled=shuffled,
        reduced=reduced,
        output_paths=output_paths,
        elapsed_seconds=time.perf_counter() - start,
        mapper_workers=workers,
    )


def run_folder(
    input_dir: str | Path = 'input',
    output_dir: str | Path = 'output',
    max_workers: int | None = None,
) -> RunResult:
    """Read all TXT splits from a folder (not recursively)."""
    directory = Path(input_dir)
    if not directory.is_dir():
        raise ValueError(f'Input folder not found: {directory}')
    paths = [p for p in directory.iterdir() if p.is_file() and p.suffix.lower() == '.txt']
    return run_mapreduce(paths, output_dir, max_workers)
