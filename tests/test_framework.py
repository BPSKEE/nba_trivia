import random
import tempfile
import ssl
from unittest.mock import patch
import unittest
from dataclasses import replace
from pathlib import Path

from nba_trivia.data import Catalog, read_csv, write_csv
from nba_trivia.game import question
from nba_trivia.scraper import SourceError, parse_team, parse_teams, tls_context


class FrameworkTests(unittest.TestCase):
    def setUp(self):
        self.rows = parse_team(Path('tests/fixtures/team.html').read_text(), 2024, 'BOS', 'Boston Celtics')

    def test_current_totals_table_id(self):
        html = Path('tests/fixtures/team.html').read_text().replace('id="totals"', 'id="totals_stats"').replace('data-stat="g"', 'data-stat="games"')
        self.assertEqual(parse_team(html, 2024, 'BOS', 'Boston Celtics'), self.rows)

    def test_tls_verification_stays_enabled(self):
        context = tls_context()
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        with patch.dict('os.environ', {'SSL_CERT_FILE': ssl.get_default_verify_paths().openssl_cafile}):
            with patch('certifi.where') as bundle:
                tls_context()
                bundle.assert_not_called()

    def test_join_totals_and_nulls(self):
        a, b = self.rows
        self.assertEqual((a.height_inches, a.jersey_number, a.minutes_total, a.ppg), (75, '00', 250, 12.3))
        self.assertEqual(a.spg, 0)
        self.assertIsNone(a.bpg)
        self.assertIsNone(b.games)

    def test_csv_roundtrip_and_sort(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'rosters.csv'
            write_csv(path, self.rows)
            self.assertEqual(read_csv(path), sorted(self.rows, key=lambda r: r.key))
            with self.assertRaises(ValueError):
                write_csv(path, self.rows * 2)
            self.assertEqual(len(read_csv(path)), 2)
        result = Catalog(self.rows).select(sort_by='ppg', descending=True, min_minutes=100)
        self.assertEqual(len(result), 1)

    def test_discovery_and_failure(self):
        html = '<table id="x"><tr><td data-stat="team"><a href="/teams/SEA/1996.html">Seattle SuperSonics*</a></td></tr></table>'
        self.assertEqual(parse_teams(html, 1996), [('SEA', 'Seattle SuperSonics')])
        with self.assertRaises(SourceError):
            parse_team('<html>blocked</html>', 2024, 'BOS', 'Boston')

    def test_modes_and_traded_player(self):
        a = self.rows[0]
        b = replace(a, player_id='other', player_name='Other', team_id='LAL', team_name='Los Angeles Lakers', ppg=20)
        trade = replace(a, team_id='NYK', team_name='New York Knicks')
        for mode in ('guess-player', 'guess-team', 'higher-stat'):
            for seed in range(20):
                q = question([a, b, trade], mode, random.Random(seed))
                self.assertIn(q.answer, q.choices)
                self.assertEqual(len(q.choices), len(set(q.choices)))
                if mode == 'guess-team' and 'Test Alpha' in q.prompt:
                    self.assertEqual(len(set(q.choices) & {'Boston Celtics', 'New York Knicks'}), 1)


if __name__ == '__main__':
    unittest.main()
