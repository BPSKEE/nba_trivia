import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from nba_trivia.gui import CourtButton, TriviaApp, AutocompleteEntry


class ClickRegressionTests(unittest.TestCase):
    def button(self):
        button = object.__new__(CourtButton)
        button.instate = Mock(return_value=False)
        button.focus_set = Mock()
        button.state = Mock()
        button.invoke = Mock()
        button.winfo_width = Mock(return_value=200)
        button.winfo_height = Mock(return_value=60)
        button._mouse_armed = button._space_armed = False
        return button

    def test_first_click_focuses_and_invokes_once_on_release(self):
        button = self.button()
        event = SimpleNamespace(x=100,y=30)
        self.assertEqual(button.mouse_press(event),'break')
        button.focus_set.assert_called_once()
        button.invoke.assert_not_called()
        self.assertEqual(button.mouse_release(event),'break')
        button.mouse_release(event)
        button.invoke.assert_called_once()

    def test_disabled_and_drag_out_do_not_invoke(self):
        button = self.button()
        button.instate.return_value = True
        button.mouse_press(SimpleNamespace(x=1,y=1))
        button.mouse_release(SimpleNamespace(x=1,y=1))
        button.invoke.assert_not_called()
        button.instate.return_value = False
        button.mouse_press(SimpleNamespace(x=1,y=1))
        button.mouse_release(SimpleNamespace(x=201,y=1))
        button.invoke.assert_not_called()

    def test_keyboard_does_not_bubble_into_root_submit(self):
        button=self.button()
        self.assertEqual(button.return_press(),'break')
        button.invoke.assert_called_once()
        button.invoke.reset_mock()
        button.space_press()
        button.space_press()
        button.space_release()
        button.space_release()
        button.invoke.assert_called_once()

    def test_setting_click_does_not_rebuild_menu(self):
        app=object.__new__(TriviaApp)
        app.mode=Mock()
        app.goal=Mock()
        app.menu=Mock()
        app.update_mode_controls=Mock()
        app.set_mode('Guess the college')
        app.set_goal('One team')
        app.menu.assert_not_called()
        self.assertEqual(app.update_mode_controls.call_count,2)

    def test_dismissing_suggestions_keeps_reserved_space(self):
        completion=object.__new__(AutocompleteEntry)
        completion.dropdown=Mock()
        completion.listbox=Mock()
        completion.suggestion_scroll=Mock()
        completion.placeholder=Mock()
        completion.hide()
        completion.dropdown.pack_forget.assert_not_called()
        completion.listbox.pack_forget.assert_called_once()
