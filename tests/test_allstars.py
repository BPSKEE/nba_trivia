import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from nba_trivia.allstars import parse_allstars,write_allstars,read_allstars,make_allstar_session,east_west_year
from nba_trivia.gui import TriviaApp
from nba_trivia.scraper import SourceError


def fixture():
    source=''
    for conference,prefix in [('East','e'),('West','w')]:
        source+=f'<table id="{conference}">'
        for i in range(12):
            source+=f'<tr><td data-stat="player"><a href="/players/{prefix}/{prefix}player{i}.html">{conference} Player {i}</a></td></tr>'
        source+='</table>'
    return source+'<a href="/players/i/injured01.html">Injured Star</a> (East): Did not play due to injury; Replaced by East Player 0<br>'


class AllStarTests(unittest.TestCase):
    def test_actual_conference_rosters_and_injury_notes(self):
        rows=parse_allstars(fixture(),2024)
        self.assertEqual(len(rows),25)
        injured=next(r for r in rows if r.player_id=='injured01')
        self.assertEqual((injured.conference,injured.player_name,injured.status),('East','Injured Star','selected_did_not_play'))
        self.assertEqual(next(r for r in rows if r.player_id=='eplayer0').player_name,'East Player 0')
        with self.assertRaises(SourceError):
            parse_allstars('<html>blocked</html>',2024)

    def test_years_and_csv_roundtrip(self):
        for year in (1976,2017,2024):self.assertTrue(east_west_year(year))
        for year in (1999,2018,2023,2025,2026):self.assertFalse(east_west_year(year))
        rows=parse_allstars(fixture(),2024)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'allstars.csv'
            write_allstars(path,rows)
            self.assertEqual(read_allstars(path),rows)
        with self.assertRaises(ValueError):make_allstar_session(rows,2025,2026)
        self.assertEqual(make_allstar_session(rows,2024,2024).anchor.season_end,2024)

    def test_guesses_require_both_rosters_and_duplicate_handling(self):
        s=make_allstar_session(parse_allstars(fixture(),2024),2024,2024)
        for _ in range(8):s.guess('Not an All Star')
        self.assertIsNone(s.outcome)
        self.assertEqual(s.guess('EAST PLAYER 0'),'Correct!')
        self.assertIn('already',s.guess('East Player 0'))
        for row in s.answers:
            if row.team_id=='East':s.guess(row.player_name)
        self.assertIsNone(s.outcome)
        for row in s.answers:
            if row.team_id=='West':s.guess(row.player_name)
        self.assertEqual(s.outcome,'victory')

    def test_side_by_side_table_updates_and_red_reveals(self):
        app=object.__new__(TriviaApp)
        app.session=make_allstar_session(parse_allstars(fixture(),2024),2024,2024)
        app.progress=Mock()
        app.allstar_tables={conf:Mock() for conf in ('East','West')}
        for table in app.allstar_tables.values():table.get_children.return_value=[]
        app.session.guess('East Player 0')
        app.refresh_table()
        east_calls=app.allstar_tables['East'].insert.call_args_list
        self.assertIn(('East Player 0',),[c.kwargs['values'] for c in east_calls])
        self.assertEqual(len(east_calls),13)
        self.assertEqual(app.allstar_tables['West'].insert.call_count,12)
        app.session.quit()
        for table in app.allstar_tables.values():table.reset_mock()
        app.refresh_table(reveal=True)
        self.assertTrue(all(c.kwargs['tags']==('revealed',) for c in app.allstar_tables['West'].insert.call_args_list))
