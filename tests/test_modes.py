import random
import unittest
from dataclasses import replace
from nba_trivia.data import PlayerSeason
from nba_trivia.modes import make_session


def roster(count=12):
    return [PlayerSeason(2024, '2023-24', 'NBA', 'BOS', 'Boston Celtics', f'p{i}', f'Player {i}',
                         position='PG', games=20, minutes_total=1000-i*80, ppg=10+i,
                         height_inches=75, jersey_number=str(i)) for i in range(count)]


class SessionTests(unittest.TestCase):
    def test_one_player_unlimited_case_and_threshold(self):
        rows = roster()
        rows[0] = replace(rows[0], minutes_total=250)
        rows[1] = replace(rows[1], minutes_total=249)
        s = make_session(rows, 'one-player', 'BOS')
        for _ in range(12):
            self.assertIn('was not on', s.guess('Nobody'))
        self.assertIsNone(s.outcome)
        self.assertIn('250-minute', s.guess('Player 1'))
        self.assertEqual(s.guess('  PLAYER 0  '), 'Correct!')
        self.assertIsNone(s.outcome)
        self.assertIn('already', s.guess('Player 0'))
        for r in s.answers:
            if r.player_id not in s.found:
                s.guess(r.player_name)
        self.assertEqual(s.outcome, 'victory')

    def test_ppg_order_unknown_last(self):
        rows = roster(4)
        rows[0] = replace(rows[0], ppg=None)
        rows[1] = replace(rows[1], ppg=0)
        rows[2] = replace(rows[2], ppg=20)
        rows[3] = replace(rows[3], minutes_total=249, ppg=30)
        s = make_session(rows, 'one-player')
        self.assertEqual([r.player_id for r in s.answers], ['p2', 'p1', 'p0'])
        s.guess('Player 1')
        self.assertEqual([r.player_id for r in s.answers], ['p2', 'p1', 'p0'])
        s.quit()
        self.assertEqual(s.outcome, 'quit')

    def test_roster_hints_duplicates_and_trades(self):
        rows = roster()
        rows.append(replace(rows[0], team_id='LAL', team_name='Los Angeles Lakers'))
        s = make_session(rows, 'one-player', 'BOS', rng=random.Random(7))
        self.assertEqual([r.player_id for r in s.answers], [f'p{i}' for i in reversed(range(10))])
        self.assertEqual(len(s.traded[('p0', 2024)]), 2)
        self.assertEqual(set(s.hint()), {'height_inches', 'jersey_number', 'ppg', 'college', 'age'})
        self.assertIsNone(s.hint())
        self.assertIn('250-minute', s.guess('Player 11'))
        s.guess('player 0')
        self.assertIn('already', s.guess('PLAYER 0'))
        for i in range(1, 10):
            s.guess(f'Player {i}')
        self.assertEqual(s.outcome, 'victory')

    def test_player_teams_selection_keeps_other_teams(self):
        a = roster(1)[0]
        b = replace(a, team_id='LAL', team_name='Los Angeles Lakers', games=10, ppg=25)
        for goal in ('one', 'all'):
            s = make_session([a, b], 'player-teams', 'BOS', goal)
            self.assertEqual(len(s.answers), 2)
            self.assertEqual(s.season_stats()['games'], 30)
            self.assertEqual(s.season_stats()['ppg'], 15)
            s.guess('los angeles lakers')
            self.assertEqual(s.outcome, 'victory' if goal == 'one' else None)
            if goal == 'all':
                s.guess('LAL')
                self.assertEqual(s.wrong, 0)
                s.guess('bos')
                self.assertEqual(s.outcome, 'victory')

    def test_five_wrong_and_quit(self):
        s = make_session(roster(1), 'player-teams')
        s.guess(' ')
        self.assertEqual(s.wrong, 0)
        for _ in range(4):
            s.guess('Wrong team')
            self.assertIsNone(s.outcome)
        s.guess('Wrong team')
        self.assertEqual(s.outcome, 'failure')
        s.guess('BOS')
        self.assertEqual(len(s.found), 0)
        s = make_session(roster(), 'one-player')
        s.quit()
        self.assertEqual(s.outcome, 'quit')
        self.assertIsNone(s.hint())

    def test_missing_required_data(self):
        a = replace(roster(1)[0], minutes_total=None)
        with self.assertRaises(ValueError):
            make_session([a], 'one-player')
        with self.assertRaises(ValueError):
            make_session(roster(9), 'top-ten')
        with self.assertRaises(ValueError):
            make_session([replace(a, games=None)], 'player-teams')

class NameNormalizationTests(unittest.TestCase):
    def test_accent_and_latin_variants(self):
        from nba_trivia.modes import normalized
        for accented, plain in [('Nikola Jokić', 'nikola jokic'), ('Ömer Aşık', 'omer asik'),
                                ('Luka Dončić', 'luka doncic'), ('Kristaps Porziņģis', 'kristaps porzingis'),
                                ('İı Øø Łł Đđ Ðð Þþ Ææ Œœ ß', 'ii oo ll dd dd thth aeae oeoe ss'),
                                ('D’Angelo', "d'angelo"), ('Jose\u0301', 'jose')]:
            self.assertEqual(normalized(accented), normalized(plain))
        s = make_session([replace(roster(1)[0], player_name='Nikola Jokić')], 'one-player')
        self.assertEqual(s.guess('NIKOLA JOKIC'), 'Correct!')
        self.assertEqual(s.anchor.player_name, 'Nikola Jokić')

class MacModeRulesTests(unittest.TestCase):
    def test_exact_thresholds_and_missing_data(self):
        a = replace(roster(1)[0], games=20, minutes_total=300)
        self.assertEqual(make_session([a], 'player-teams').answers, [a])
        at250 = replace(a, games=16, minutes_total=250)
        self.assertEqual(make_session([at250], 'player-teams').answers, [at250])
        for row in (replace(a, minutes_total=299), replace(at250, minutes_total=249),
                    replace(a, minutes_total=None), replace(a, games=None)):
            with self.assertRaises(ValueError):
                make_session([row], 'player-teams')

    def test_season_thresholds_preserve_short_stints(self):
        a = replace(roster(1)[0], games=10, minutes_total=200)
        b = replace(a, team_id='LAL', team_name='Los Angeles Lakers', games=10, minutes_total=100)
        session = make_session([a,b], 'player-teams', 'LAL')
        self.assertEqual({r.team_id for r in session.answers}, {'BOS','LAL'})
        self.assertEqual(session.season_stats()['minutes_total'], 300)
        with self.assertRaises(ValueError):
            make_session([a, replace(b, minutes_total=99)], 'player-teams')

    def test_team_buttons_use_exact_historical_season(self):
        a = roster(1)[0]
        historic = replace(a, player_id='historic', team_id='SEA', team_name='Seattle SuperSonics')
        later = replace(a, season_end=2025, team_id='OKC', team_name='Oklahoma City Thunder')
        session = make_session([a,historic,later], 'player-teams', 'BOS')
        self.assertEqual(session.team_options, [('BOS','Boston Celtics'), ('SEA','Seattle SuperSonics')])
        self.assertEqual(session.guess('SEA').split('Incorrect')[0].strip(),
                         'Player 0 did not play for SEA in 2024.')

    def test_four_modes(self):
        from nba_trivia.modes import MODE_NAMES
        self.assertEqual(set(MODE_NAMES.values()), {'one-player','player-teams','college','all-stars'})
        with self.assertRaises(ValueError):
            make_session(roster(), 'top-ten')

class CombinedHintTests(unittest.TestCase):
    def test_single_click_reveals_all_five_and_cannot_repeat(self):
        s = make_session(roster(),'one-player')
        self.assertEqual(set(s.hint()), {'jersey_number','height_inches','ppg','college','age'})
        self.assertEqual(set(s.revealed_hints), set(s.hint_fields))
        self.assertEqual(s.hints, [])
        self.assertIsNone(s.hint())
        self.assertEqual(s.found, set())
