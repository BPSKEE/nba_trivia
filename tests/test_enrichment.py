import csv
import tempfile
import unittest
from dataclasses import asdict, replace
from pathlib import Path

from nba_trivia.data import PlayerSeason, LEGACY_COLUMNS, read_csv, write_csv
from nba_trivia.modes import make_session
from nba_trivia.scraper import parse_team, collect


class EnrichmentTests(unittest.TestCase):
    def html(self, awards='AS,NBA1', has_awards=True):
        html = Path('tests/fixtures/team.html').read_text()
        html = html.replace('<td data-stat="pos">PG</td>', '<td data-stat="pos">PG</td><td data-stat="college">College A, College B</td>')
        additions = '<td data-stat="age">25</td>'
        if has_awards:
            additions += f'<td data-stat="awards">{awards}</td>'
        return html.replace('<td data-stat="g">10</td>', additions + '<td data-stat="g">10</td>')

    def test_source_fields_and_unknowns(self):
        a,b = parse_team(self.html(),2024,'BOS','Boston')
        self.assertEqual((a.age,a.is_all_star,a.college),(25,1,'College A, College B'))
        self.assertEqual((b.age,b.is_all_star,b.college),(None,None,''))
        for awards in ('', 'NBA1', 'DPOY-1,ASG-MVP'):
            self.assertEqual(parse_team(self.html(awards),2024,'BOS','Boston')[0].is_all_star,0)
        self.assertIsNone(parse_team(self.html(has_awards=False),2024,'BOS','Boston')[0].is_all_star)

    def test_enriched_roundtrip_and_legacy_compatibility(self):
        rows = parse_team(self.html(),2024,'BOS','Boston')
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'new.csv'
            write_csv(path,rows)
            self.assertEqual(read_csv(path),sorted(rows,key=lambda r:r.key))
            old=Path(folder)/'old.csv'
            with old.open('w',newline='') as stream:
                writer=csv.DictWriter(stream,fieldnames=LEGACY_COLUMNS)
                writer.writeheader()
                writer.writerow({k:v for k,v in asdict(rows[0]).items() if k in LEGACY_COLUMNS})
            legacy=read_csv(old)[0]
            self.assertEqual((legacy.age,legacy.is_all_star,legacy.college),(None,None,''))

    def test_optional_hints_and_false_is_known(self):
        row = parse_team(self.html(awards=''),2024,'BOS','Boston')[0]
        session=make_session([row],'one-player')
        self.assertEqual(set(session.hints),{'height_inches','jersey_number','ppg','age','college'})
        old=replace(row,age=None,is_all_star=None,college='')
        self.assertEqual(len(make_session([old],'one-player').hints),5)

    def test_collection_reconciles_traded_all_star_without_touching_input(self):
        parent=self
        class FakeClient:
            def get(self,path):
                if '/leagues/' in path:
                    return '<table id="teams"><tr><td data-stat="x"><a href="/teams/BOS/2024.html">Boston</a></td><td data-stat="y"><a href="/teams/LAL/2024.html">Los Angeles</a></td></tr></table>'
                return parent.html('AS' if '/BOS/' in path else '')
        with tempfile.TemporaryDirectory() as folder:
            rows=collect(FakeClient(),2024,2024,Path(folder)/'new.csv',progress=lambda *a,**k:None)
            self.assertEqual([r.is_all_star for r in rows if r.player_id=='testaa01'],[1,1])
