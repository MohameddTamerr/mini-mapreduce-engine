"""Run from project root: python -m unittest discover -s tests -v"""

import tempfile
import unittest
from pathlib import Path

from engine import combiner, mapper, partitioner, run_folder, run_mapreduce, tokenize


class MapReduceTests(unittest.TestCase):
    def test_mapper_emits_one_for_every_occurrence(self):
        self.assertEqual(mapper('Cat, CAT! dog.'), [('cat', 1), ('cat', 1), ('dog', 1)])

    def test_combiner_is_local(self):
        pairs = [('cat', 1), ('cat', 1), ('dog', 1)]
        self.assertEqual(combiner(pairs), {'cat': 2, 'dog': 1})

    def test_unicode_arabic_support(self):
        self.assertEqual(tokenize('بيانات، بيانات! Data DATA 2026'), ['بيانات', 'بيانات', 'data', 'data'])

    def test_partition_rule_is_consistent(self):
        self.assertEqual(partitioner('cat'), partitioner('cat'))
        self.assertIn(partitioner('cat'), (0, 1))

    def test_two_files_reducer_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            input_dir = base / 'input'
            input_dir.mkdir()
            (input_dir / 'one.txt').write_text('Cat dog cat', encoding='utf-8')
            (input_dir / 'two.txt').write_text('dog bird CAT', encoding='utf-8')
            result = run_folder(input_dir, base / 'output')
            self.assertEqual(len(result.traces), 2)
            self.assertEqual(result.mapper_workers, 2)
            self.assertEqual(result.total_words, 6)
            self.assertEqual(result.totals, {'bird': 1, 'cat': 3, 'dog': 2})
            self.assertEqual(len(result.output_paths), 2)
            self.assertTrue(all(path.exists() for path in result.output_paths))
            self.assertEqual(sum(len(item) for item in result.reduced), 3)
            self.assertEqual(result.output_paths[0].read_text(encoding='utf-8').count('cat: '),
                             1 if partitioner('cat') == 0 else 0)

    def test_empty_txt_creates_two_empty_reducer_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'empty.txt'
            path.write_text('', encoding='utf-8')
            result = run_mapreduce([path], Path(tmp) / 'out')
            self.assertEqual(result.total_words, 0)
            self.assertEqual(result.unique_words, 0)
            self.assertTrue(all(p.read_text(encoding='utf-8') == '' for p in result.output_paths))

    def test_no_files_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'No .txt files'):
                run_folder(tmp, Path(tmp) / 'out')


if __name__ == '__main__':
    unittest.main()
