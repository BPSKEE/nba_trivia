import random
import unittest
from dataclasses import replace
from nba_trivia.autocomplete import NameIndex
from nba_trivia.data import PlayerSeason
from nba_trivia.gui import select_range
from nba_trivia.modes import make_session, college_names


class CollegeModeTests(unittest.TestCase):
    def setUp(self):
        self.row=PlayerSeason(2024,'2023-24','NBA','BOS','Boston Celtics','p','Player',games=80,minutes_total=2000,college='College A, Université B')

    def test_any_school_accepted_case_accent_and_unlimited(self):
        for guess in ['college a','UNIVERSITE B']:
            s=make_session([self.row],'college')
            for _ in range(10):
                self.assertIn('not a listed college', s.guess('Wrong School'))
            self.assertIsNone(s.outcome)
            self.assertEqual(s.guess(' '),'Enter a name before submitting.')
            self.assertEqual(s.guess(guess),'Correct!')
            self.assertEqual(s.outcome,'victory')

    def test_range_uses_actual_played_seasons(self):
        other=replace(self.row,season_end=2020,player_id='other',player_name='Other')
        selected=select_range([other,self.row],2024,2024)
        self.assertEqual(make_session(selected,'college').anchor.player_id,'p')
        for row in [replace(self.row,games=0),replace(self.row,games=None),replace(self.row,college='')]:
            with self.assertRaises(ValueError):
                make_session([row],'college')

    def test_team_filter_and_all_colleges_from_selected_player(self):
        other=replace(self.row,team_id='LAL',college='College C')
        s=make_session([self.row,other],'college',team='BOS')
        self.assertEqual(s.anchor.team_id,'BOS')
        self.assertEqual(s.colleges,['College A','College C','Université B'])
        with self.assertRaises(ValueError):
            make_session([self.row],'college',team='NYK')
        s.quit()
        self.assertEqual(s.label(s.anchor),'College A, College C, Université B')
        self.assertEqual(s.outcome,'quit')

    def test_school_completion_index_and_no_college_hint(self):
        index=NameIndex(college_names(self.row.college))
        self.assertEqual(index.matches('universite'),['Université B'])
        self.assertEqual(index.matches('college'),['College A'])
        self.assertIsNone(make_session([self.row],'college').hint())

class CareerMinutesRuleTests(unittest.TestCase):
    def test_exact_threshold_and_weighting(self):
        from nba_trivia.modes import career_mpg_index
        a=PlayerSeason(2023,'2022-23','NBA','BOS','Boston','p','Player',games=10,minutes_total=400,college='Duke')
        b=replace(a,season_end=2024,games=90,minutes_total=2100)
        self.assertEqual(career_mpg_index([a,b])['p'],25)
        self.assertEqual(make_session([b],'college',career_rows=[a,b]).career_mpg,25)
        with self.assertRaises(ValueError):
            make_session([a],'college',career_rows=[a,replace(b,minutes_total=2099)])

    def test_range_and_team_do_not_change_career_average(self):
        a=PlayerSeason(2023,'2022-23','NBA','BOS','Boston','p','Player',games=40,minutes_total=400,college='Duke')
        b=replace(a,season_end=2024,team_id='LAL',games=40,minutes_total=1600)
        s=make_session([a],'college',team='BOS',career_rows=[a,b])
        self.assertEqual(s.career_mpg,25)
        with self.assertRaises(ValueError):
            make_session([b],'college',career_rows=[replace(a,minutes_total=399),b])

    def test_missing_history_and_coverage_boundary(self):
        from nba_trivia.modes import career_mpg_index
        a=PlayerSeason(1976,'1975-76','NBA','BOS','Boston','old','Old',games=10,minutes_total=300,college='Duke')
        b=replace(a,season_end=2024,player_id='new')
        self.assertNotIn('old',career_mpg_index([a,b],exclude_boundary=True))
        self.assertEqual(career_mpg_index([a,b],exclude_boundary=True)['new'],30)
        self.assertNotIn('new',career_mpg_index([b,replace(b,season_end=2025,minutes_total=None)]))

class CareerTotalMinutesTests(unittest.TestCase):
    def test_2000_is_inclusive_and_both_rules_required(self):
        row=PlayerSeason(2024,'2023-24','NBA','BOS','Boston','p','Player',games=80,minutes_total=2000,college='Duke')
        session=make_session([row],'college')
        self.assertEqual(session.career_minutes,2000)
        for excluded in (replace(row,games=50,minutes_total=1999),replace(row,games=81)):
            with self.assertRaises(ValueError):
                make_session([excluded],'college')

    def test_minutes_sum_across_seasons_and_traded_stints(self):
        row=PlayerSeason(2023,'2022-23','NBA','BOS','Boston','p','Player',games=40,minutes_total=1000,college='Duke')
        other=replace(row,season_end=2024,team_id='LAL')
        session=make_session([other],'college',team='LAL',career_rows=[row,other])
        self.assertEqual(session.career_minutes,2000)
        self.assertEqual(session.career_mpg,25)
