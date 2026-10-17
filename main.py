"""Command-line version. Streamlit GUI lives in app.py, NOT main.py."""

import argparse
from engine import run_folder


def main():
    parser = argparse.ArgumentParser(description='Mini MapReduce Word Count (no Spark/Hadoop).')
    parser.add_argument('--input', default='input', help='Folder of .txt files')
    parser.add_argument('--output', default='output', help='Output folder')
    parser.add_argument('--workers', type=int, default=None, help='Mapper threads (default: one per input file)')
    args = parser.parse_args()

    print('\nMINI MAPREDUCE | WORD COUNT')
    print('-' * 48)
    try:
        result = run_folder(args.input, args.output, args.workers)
    except (ValueError, UnicodeError, OSError) as exc:
        parser.exit(1, f'Error: {exc}\n')

    print(f'Input files (splits): {len(result.traces)}')
    print(f'Mapper worker threads: {result.mapper_workers}')
    print(f'Number of (word, 1) emissions: {result.total_words:,}')
    print(f'Unique words: {result.unique_words:,}')
    print(f'Elapsed time: {result.elapsed_seconds:.4f} seconds')
    print('\nStages: INPUT -> MAP (parallel) -> COMBINE -> PARTITION -> SHUFFLE/SORT -> REDUCE')
    print('\nTop 15 words across BOTH reducers:')
    for word, count in sorted(result.totals.items(), key=lambda pair: (-pair[1], pair[0]))[:15]:
        print(f'  {word:<18} {count:>5}')
    print('\nOutput files:')
    for i, path in enumerate(result.output_paths):
        print(f'  Reducer {i}: {path} ({len(result.reduced[i])} unique words)')
    print('\nSuccess! You can also launch the GUI with: streamlit run app.py\n')


if __name__ == '__main__':
    main()
