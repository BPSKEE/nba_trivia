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

class BundledDataTests(unittest.TestCase):
    def test_packaged_csv_is_preferred(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from nba_trivia.gui import default_roster_path
        with tempfile.TemporaryDirectory() as folder:
            csv_path = Path(folder) / 'data/rosters.csv'
            csv_path.parent.mkdir()
            csv_path.write_text('bundled test')
            with patch('sys.frozen', True, create=True), patch('sys._MEIPASS', folder, create=True):
                self.assertEqual(default_roster_path(), csv_path)
                csv_path.unlink()
                self.assertNotEqual(default_roster_path(), csv_path)

class RosterTableTests(unittest.TestCase):
    def test_hints_and_red_reveal_preserve_correct_answers(self):
        from unittest.mock import Mock
        from nba_trivia.gui import TriviaApp
        from nba_trivia.modes import make_session
        rows = [PlayerSeason(2024,'2023-24','NBA','BOS','Boston Celtics',str(i),f'Player {i}',
                             position='PG',games=20,minutes_total=300,ppg=20-i,
                             height_inches=75,jersey_number=str(i)) for i in range(2)]
        app = object.__new__(TriviaApp)
        app.session = make_session(rows,'one-player')
        app.table = Mock()
        app.table.get_children.return_value = []
        app.progress = Mock()
        app.refresh_table()
        values = app.table.insert.call_args_list[0].kwargs['values']
        self.assertEqual(values[0], '________________')
        self.assertEqual(values[4:], ('Hidden',)*5)
        app.session.hints = ['ppg']
        app.session.hint()
        app.table.reset_mock()
        app.refresh_table()
        self.assertEqual(app.table.insert.call_args_list[0].kwargs['values'][6], '20')
        app.session.guess('Player 0')
        app.session.quit()
        app.table.reset_mock()
        app.refresh_table(reveal=True)
        calls = app.table.insert.call_args_list
        self.assertEqual(calls[0].kwargs['tags'], ())
        self.assertEqual(calls[1].kwargs['tags'], ('revealed',))

class AllStarRowTests(unittest.TestCase):
    def test_star_image_gold_tag_and_red_reveal_coexist(self):
        from unittest.mock import Mock
        from nba_trivia.gui import TriviaApp
        from nba_trivia.modes import make_session
        star = PlayerSeason(2024,'2023-24','NBA','BOS','Boston','a','Star Player',games=20,
                            minutes_total=300,ppg=20,is_all_star=1,age=25,college='Duke')
        other = replace(star,player_id='b',player_name='Other',ppg=10,is_all_star=0)
        app = object.__new__(TriviaApp)
        app.session = make_session([star,other],'one-player')
        app.table = Mock()
        app.table.get_children.return_value = []
        app.progress = Mock()
        app.star_icon = 'star-image'
        app.refresh_table()
        calls = app.table.insert.call_args_list
        self.assertEqual(calls[0].kwargs['tags'], ('all_star',))
        self.assertEqual(calls[0].kwargs['image'], 'star-image')
        self.assertEqual(calls[1].kwargs['image'], '')
        app.session.hint()
        app.table.reset_mock()
        app.refresh_table()
        values=app.table.insert.call_args_list[0].kwargs['values']
        self.assertEqual(values[-3:], ('20','Duke','25'))
        self.assertEqual(values[0], '________________')
        app.session.quit()
        app.table.reset_mock()
        app.refresh_table(reveal=True)
        self.assertEqual(app.table.insert.call_args_list[0].kwargs['tags'], ('revealed','all_star'))
