"""Routing metadata must preserve exact names and only expose reviewed grids."""
import unittest

from build_manifests import approved_grids


class RuntimeGridIndexTests(unittest.TestCase):
    def test_only_reviewed_headers_and_exact_names(self):
        names = ['Assets/シナリオ.xlsx:Ａ ', 'Assets/シナリオ.xlsx:A', 'unused']
        document = {
            'headers': [dict(grid_index=i, header_row_index_0based=0, grid_name=name)
                        for i, name in enumerate(names)],
            'rows': [dict(grid_index=i, header_row_index_0based=0) for i in [0, 1, 0]],
        }
        self.assertEqual(approved_grids(document), sorted(names[:2]))
        document['rows'] = []
        self.assertEqual(approved_grids(document), [])

    def test_missing_header_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'missing its header'):
            approved_grids({'headers': [], 'rows': [dict(grid_index=0, header_row_index_0based=1)]})


if __name__ == '__main__':
    unittest.main()
