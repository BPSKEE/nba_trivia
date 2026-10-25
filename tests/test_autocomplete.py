import unittest
from nba_trivia.autocomplete import NameIndex


class AutocompleteTests(unittest.TestCase):
    def test_prefix_first_last_and_accents(self):
        index = NameIndex(['Nikola Jokić', 'Nikola Vučević', 'LeBron James', 'Ömer Aşık'])
        self.assertEqual(index.matches('nik'), ['Nikola Jokić', 'Nikola Vučević'])
        self.assertEqual(index.matches('jok'), ['Nikola Jokić'])
        self.assertEqual(index.matches(' NIKOLA J '), ['Nikola Jokić'])
        self.assertEqual(index.matches('omer'), ['Ömer Aşık'])
        self.assertEqual(index.matches('asik'), ['Ömer Aşık'])
        self.assertEqual(index.matches(''), [])
        self.assertEqual(index.matches('no such name'), [])

    def test_all_names_no_answer_filter_or_limit(self):
        index = NameIndex(['Player '+str(i) for i in range(30)] + ['Player 1'])
        self.assertEqual(len(index.matches('Player')), 30)

    def test_accept_fills_without_submitting(self):
        from unittest.mock import Mock
        from nba_trivia.gui import AutocompleteEntry
        completion = object.__new__(AutocompleteEntry)
        completion.listbox = Mock()
        completion.listbox.curselection.return_value = (0,)
        completion.listbox.get.return_value = 'Nikola Jokić'
        completion.entry = Mock()
        completion.variable = Mock()
        completion.hide = Mock()
        completion.after_idle = Mock()
        self.assertEqual(completion.accept(), 'break')
        completion.variable.set.assert_called_once_with('Nikola Jokić')
        completion.hide.assert_called_once()
