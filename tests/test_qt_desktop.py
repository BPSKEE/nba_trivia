"""Exercise actual Qt widgets and mouse events without controlling the user's desktop."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
from PySide6.QtCore import Qt, QPoint
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from nba_trivia.qt_gui import TriviaWindow
from nba_trivia.autocomplete import NameIndex
from nba_trivia.modes import make_session
from nba_trivia.allstars import AllStarPlayer,make_allstar_session
from nba_trivia.data import PlayerSeason


class QtDesktopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        cls.app.setStyle('Fusion')

    def setUp(self):
        self.window=TriviaWindow(autoload=False)
        self.window.show()
        self.pump()

    def pump(self):
        for _ in range(5):self.app.processEvents()

    def tearDown(self):
        self.window.close();self.window.deleteLater();self.pump()

    def test_repeated_real_clicks_keep_controls_in_place(self):
        controls=self.window.mode_buttons
        original={mode:b.geometry() for mode,b in controls.items()}
        for _ in range(5):
            for mode,b in controls.items():
                QTest.mouseClick(b,Qt.MouseButton.LeftButton)
                self.pump()
                self.assertEqual(self.window.selected_mode(),mode)
                self.assertEqual(b.geometry(),original[mode])
        QTest.mouseClick(controls['player-teams'],Qt.MouseButton.LeftButton)
        QTest.mouseClick(self.window.one_goal,Qt.MouseButton.LeftButton)
        self.assertTrue(self.window.one_goal.isChecked())
        QTest.mouseClick(self.window.all_goal,Qt.MouseButton.LeftButton)
        self.assertTrue(self.window.all_goal.isChecked())

    def test_real_autocomplete_click_fills_then_submit_wins(self):
        row=PlayerSeason(2024,'2023-24','NBA','BOS','Boston','p','Player',games=80,minutes_total=2400,college='Duke University')
        self.window.college_names=NameIndex(['Duke University','Other University'])
        self.window.show_game(make_session([row],'college'))
        self.pump()
        entry=self.window.entry
        button=self.window.submit_button
        original=button.geometry()
        QTest.keyClicks(entry,'Duk')
        self.pump()
        popup=entry.completion.popup()
        self.assertTrue(popup.isVisible())
        QTest.mouseClick(popup.viewport(),Qt.MouseButton.LeftButton,pos=popup.visualRect(popup.model().index(0,0)).center())
        self.pump()
        self.assertEqual(entry.text(),'Duke University')
        self.assertIsNone(self.window.session.outcome)
        self.assertEqual(button.geometry(),original)
        QTest.mouseClick(button,Qt.MouseButton.LeftButton)
        self.pump()
        self.assertEqual(self.window.session.outcome,'victory')
        QTest.mouseClick(self.window.back_button,Qt.MouseButton.LeftButton)
        self.assertIs(self.window.stack.currentWidget(),self.window.menu_page)

    def test_all_star_metadata_wraps_without_horizontal_scroll(self):
        stars=[]
        for conf in ('East','West'):
            stars += [AllStarPlayer(2024,conf,f'{conf}{i}',f'{conf} Player {i}','game_roster','source') for i in range(12)]
        metadata=[PlayerSeason(2024,'2023-24','NBA','BOS','Boston Celtics','East0','East Player 0',games=20,age=25,college='A Very Long College Name That Must Wrap Inside Its Column'),
                  PlayerSeason(2024,'2023-24','NBA','LAL','Los Angeles Lakers','East0','East Player 0',games=10,age=25,college='A Very Long College Name That Must Wrap Inside Its Column')]
        s=make_allstar_session(stars,2024,2024,season_rows=metadata)
        self.window.show_game(s)
        for width in (1000,1220,1450):
            self.window.resize(width,940);self.pump()
            for table in self.window.tables.values():
                self.assertEqual(table.columnCount(),4)
                self.assertEqual(table.horizontalScrollBar().maximum(),0)
                self.assertEqual(table.horizontalScrollBarPolicy(),Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table=self.window.tables['East']
        self.assertEqual(table.item(0,0).text(),'________________')
        self.assertIn('Boston Celtics',table.item(0,1).text())
        self.assertIn('Los Angeles Lakers',table.item(0,1).text())
        self.assertEqual(table.item(0,2).text(),'25')
        self.assertGreater(table.rowHeight(0),35)
        QTest.mouseClick(self.window.quit_button,Qt.MouseButton.LeftButton)
        self.assertEqual(table.item(0,0).text(),'East Player 0')
        self.assertEqual(table.item(0,0).foreground().color().name(),'#b42318')

    def test_roster_hint_submit_star_and_quit_buttons(self):
        from dataclasses import replace
        star=PlayerSeason(2024,'2023-24','NBA','BOS','Boston','p','Nikola Jokić',games=20,
                          minutes_total=500,ppg=25,height_inches=83,jersey_number='15',age=28,
                          college='Example College',is_all_star=1)
        other=replace(star,player_id='other',player_name='Other Player',is_all_star=0,ppg=15)
        self.window.player_names=NameIndex([star.player_name,other.player_name])
        self.window.show_game(make_session([star,other],'one-player'))
        self.pump()
        table=self.window.tables['roster']
        self.assertFalse(table.item(0,0).icon().isNull())
        self.assertEqual(table.item(0,0).background().color().name(),'#fff0bf')
        self.assertEqual(table.item(0,7).text(),'Hidden')
        QTest.mouseClick(self.window.hint_button,Qt.MouseButton.LeftButton)
        self.assertEqual(table.item(0,7).text(),'Example College')
        self.assertFalse(self.window.hint_button.isEnabled())
        self.window.entry.setText('Wrong name')
        QTest.mouseClick(self.window.submit_button,Qt.MouseButton.LeftButton)
        self.assertEqual(self.window.entry.text(),'Wrong name')
        self.window.entry.setText('Nikola Jokic')
        QTest.mouseClick(self.window.submit_button,Qt.MouseButton.LeftButton)
        self.assertEqual(table.item(0,0).text(),'Nikola Jokić')
        QTest.mouseClick(self.window.quit_button,Qt.MouseButton.LeftButton)
        self.assertEqual(table.item(1,0).foreground().color().name(),'#b42318')

    def test_team_grid_real_clicks_end_after_five_wrong(self):
        from dataclasses import replace
        correct=PlayerSeason(2024,'2023-24','NBA','BOS','Boston','p','Player',games=20,minutes_total=500)
        rows=[correct]+[replace(correct,team_id=f'X{i}',team_name=f'Team {i}',player_id=f'other{i}') for i in range(5)]
        self.window.show_game(make_session(rows,'player-teams',team='BOS'))
        self.pump()
        for i in range(5):
            QTest.mouseClick(self.window.team_buttons[f'X{i}'],Qt.MouseButton.LeftButton)
            self.assertEqual(self.window.session.wrong,i+1)
        self.assertEqual(self.window.session.outcome,'failure')
        self.assertFalse(self.window.team_buttons['BOS'].isEnabled())
