import unittest
from dataclasses import replace
from nba_trivia.data import PlayerSeason
from nba_trivia.gui import select_range

class RangeTests(unittest.TestCase):
    def test_bounds_and_missing_years(self):
        row = PlayerSeason(1976, '1975-76', 'NBA', 'BOS', 'Boston', 'one', 'One')
        self.assertEqual(select_range([row], 1976, 1976), [row])
        for start, end in [(1975,1976),(1977,1976),(1976,1977)]:
            with self.assertRaises(ValueError):
                select_range([row], start, end)
        self.assertEqual(select_range([row, replace(row, season_end=1977)],1976,1977)[1].season_end,1977)
