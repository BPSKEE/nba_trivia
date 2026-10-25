"""Qt desktop frontend: standard native event handling and stable widget layouts."""
import queue
import sys
import threading
import math
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QStringListModel
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap, QPolygonF
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QPushButton, QLineEdit, QSpinBox, QComboBox, QRadioButton,
    QButtonGroup, QCompleter, QStackedWidget, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QFileDialog, QScrollArea)

from .paths import MIN_YEAR, latest_season, default_roster_path, allstars_path, select_range
from .data import read_csv
from .modes import MODE_NAMES, make_session, college_names
from .allstars import read_allstars, make_allstar_session
from .autocomplete import NameIndex

GREEN='#173e32'
GOLD='#fff0bf'
RED='#b42318'

STYLE='''
QMainWindow,QWidget {background:#f5f2e9;color:#18312b;font-family:Helvetica;font-size:14px;}
QLabel#brand {font-size:23px;font-weight:bold;letter-spacing:2px;}
QLabel#headline {font-family:Georgia;font-size:29px;}
QLabel#muted {color:#64715f;font-size:12px;}
QPushButton {background:#e3e8db;border:1px solid #b8c5af;border-radius:6px;padding:12px 14px;min-height:24px;font-weight:bold;}
QPushButton:hover {background:#d2dfc6;border-color:#567757;}
QPushButton:pressed {background:#b9cdae;}
QPushButton:checked,QPushButton[primary="true"] {background:#173e32;color:#fffdf7;}
QPushButton:disabled {color:#8a9287;background:#e9e9df;}
QPushButton:focus {border:2px solid #ad7809;}
QPushButton[result="wrong"] {background:#f6dfd7;color:#b42318;}
QPushButton[result="correct"] {background:#173e32;color:#fffdf7;}
QLineEdit,QSpinBox,QComboBox {background:#fffdf7;border:1px solid #aabb9e;border-radius:5px;padding:10px;font-size:16px;min-height:22px;}
QSpinBox::up-button,QSpinBox::down-button {width:26px;}
QTableWidget {background:#fffdf7;gridline-color:#d8decf;border:1px solid #c9d2bf;selection-background-color:#e3e8db;}
QTableWidget::item {padding:5px;}
QHeaderView::section {background:#e3e8db;border:0;border-bottom:1px solid #b8c5af;padding:8px;font-weight:bold;}
QAbstractItemView {background:#fffdf7;selection-background-color:#173e32;selection-color:white;}
QRadioButton {spacing:8px;padding:8px;}
QRadioButton::indicator {width:20px;height:20px;}
QScrollArea {border:0;}
'''


def label(text='', name=None):
    widget=QLabel(text)
    widget.setWordWrap(True)
    if name:widget.setObjectName(name)
    return widget


def button(text,callback=None,primary=False):
    widget=QPushButton(text)
    widget.setAutoDefault(False)
    widget.setDefault(False)
    widget.setProperty('primary',primary)
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    if callback:widget.clicked.connect(callback)
    return widget


class CompletionInput(QLineEdit):
    def __init__(self,parent=None):
        super().__init__(parent)
        self.index=NameIndex([])
        self.skip_return=False
        self.model=QStringListModel(self)
        self.completion=QCompleter(self.model,self)
        self.completion.setCompletionMode(QCompleter.CompletionMode.UnfilteredPopupCompletion)
        self.setCompleter(self.completion)
        self.textEdited.connect(self.suggest)
        self.completion.activated[str].connect(self.choose)

    def suggest(self,text):
        matches=self.index.matches(text)
        self.model.setStringList(matches)
        if matches:
            self.completion.setCompletionPrefix('')
            self.completion.complete()
        else:self.completion.popup().hide()

    def choose(self,text):
        self.setText(text)
        self.skip_return=True
        self.completion.popup().hide()
        QTimer.singleShot(0,self.clear_guard)

    def clear_guard(self):self.skip_return=False


def star_icon():
    pixmap=QPixmap(20,20)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter=QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    points=QPolygonF([QPointF(10+(9 if i%2==0 else 4)*math.cos(-math.pi/2+i*math.pi/5),
                              10+(9 if i%2==0 else 4)*math.sin(-math.pi/2+i*math.pi/5)) for i in range(10)])
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor('#ad7809'))
    painter.drawPolygon(points)
    painter.end()
    return QIcon(pixmap)


class WrapTable(QTableWidget):
    def resizeEvent(self,event):
        super().resizeEvent(event)
        QTimer.singleShot(0,self.resizeRowsToContents)


class TriviaWindow(QMainWindow):
    def __init__(self,autoload=True):
        super().__init__()
        self.setWindowTitle('Courtside · NBA Trivia')
        self.resize(1220,940)
        self.setMinimumSize(1000,720)
        self.setStyleSheet(STYLE)
        self.stack=QStackedWidget()
        self.setCentralWidget(self.stack)
        self.data_path=default_roster_path()
        self.events=queue.Queue()
        self.busy=False
        self.rows=[]
        self.player_names=NameIndex([])
        self.college_names=NameIndex([])
        self.icon=star_icon()
        self.game_page=None
        self.build_menu()
        self.timer=QTimer(self)
        self.timer.timeout.connect(self.poll)
        self.timer.start(50)
        if autoload and self.data_path.exists():self.load(False)

    def build_menu(self):
        scroll=QScrollArea()
        scroll.setWidgetResizable(True)
        self.menu_page=scroll
        page=QWidget()
        scroll.setWidget(page)
        layout=QVBoxLayout(page)
        layout.setContentsMargins(30,24,30,24)
        layout.setSpacing(12)
        layout.addWidget(label('◉  COURTSIDE','brand'))
        layout.addWidget(label('NBA TRIVIA CLUB / THE ROSTER ROOM','muted'))
        layout.addWidget(label('You know the stars. Know the roster?','headline'))
        self.mode_group=QButtonGroup(self)
        self.mode_buttons={}
        grid=QGridLayout()
        descriptions=['COMPLETE THE ROSTER\nName every player with 250+ minutes',
                      "FIND THE TEAMS\nPick a player's teams for the season",
                      'GUESS THE COLLEGE\nFind the school behind the player',
                      'EAST / WEST ALL-STARS\nComplete both conference rosters']
        for i,((name,mode),description) in enumerate(zip(MODE_NAMES.items(),descriptions)):
            control=button(description)
            control.setCheckable(True)
            control.setMinimumHeight(70)
            self.mode_group.addButton(control,i)
            self.mode_buttons[mode]=control
            grid.addWidget(control,i//2,i%2)
        self.mode_buttons['one-player'].setChecked(True)
        grid.setColumnStretch(0,1);grid.setColumnStretch(1,1)
        layout.addLayout(grid)
        years=QHBoxLayout()
        self.start=QSpinBox();self.end=QSpinBox()
        for title,control,value in [('FIRST SEASON ENDING YEAR',self.start,1976),('LAST SEASON ENDING YEAR',self.end,latest_season())]:
            control.setRange(MIN_YEAR,latest_season());control.setValue(value)
            column=QVBoxLayout();column.addWidget(label(title,'muted'));column.addWidget(control);years.addLayout(column)
        layout.addLayout(years)
        layout.addWidget(label('1976 means the 1975–76 season. Choose the same start/end year for one season.','muted'))
        self.team=QComboBox();self.team.setEditable(True);self.team.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.team.addItem('All teams',None)
        self.team.completer().setFilterMode(Qt.MatchFlag.MatchContains)
        layout.addWidget(label('TEAM · TYPE TO SEARCH','muted'));layout.addWidget(self.team)
        goals=QHBoxLayout()
        goals.addWidget(label('FIND THE TEAMS GOAL','muted'))
        self.one_goal=QRadioButton('One team');self.all_goal=QRadioButton('All teams');self.all_goal.setChecked(True)
        goals.addWidget(self.one_goal);goals.addWidget(self.all_goal);goals.addStretch()
        layout.addLayout(goals)
        self.help=label('', 'muted');layout.addWidget(self.help)
        self.mode_group.buttonClicked.connect(self.update_mode)
        self.update_mode()
        self.start_button=button('STEP ONTO THE COURT  ↗',lambda:self.load(True),True)
        layout.addWidget(self.start_button)
        files=QHBoxLayout()
        self.file_button=button('Choose CSV…',self.choose_file)
        self.reload_button=button('Reload data',lambda:self.load(False))
        files.addWidget(self.file_button);files.addWidget(self.reload_button);files.addStretch()
        layout.addLayout(files)
        self.status=label('Ready. Choose your settings.','muted');layout.addWidget(self.status)
        layout.addStretch()
        self.stack.addWidget(scroll)

    def selected_mode(self):
        return next(key for key,control in self.mode_buttons.items() if control.isChecked())

    def update_mode(self,*args):
        mode=self.selected_mode()
        self.one_goal.setEnabled(mode=='player-teams');self.all_goal.setEnabled(mode=='player-teams')
        self.team.setEnabled(mode!='all-stars')
        self.help.setText({'one-player':'250+ team minutes · Complete every name · One button reveals all five hints',
                          'player-teams':'250+ season minutes and 15+ MPG · Five incorrect selections allowed',
                          'college':'25+ career MPG and 2,000+ career minutes · School autocomplete',
                          'all-stars':'Actual East/West games: 1976–2017 except 1999, plus 2024 · Team filter ignored'}[mode])

    def choose_file(self):
        path,_=QFileDialog.getOpenFileName(self,'Choose roster CSV',str(self.data_path.parent),'CSV files (*.csv)')
        if path:self.data_path=Path(path);self.load(False)

    def load(self,play):
        if self.busy:return
        start,end=self.start.value(),self.end.value()
        if end<start:self.status.setText('Finish year must be at least the start year.');return
        mode=self.selected_mode()
        index=self.team.findText(self.team.currentText())
        if mode!='all-stars' and index<0:self.status.setText('Choose a team from the list, or All teams.');return
        team=self.team.itemData(index) if index>=0 else None
        goal='one' if self.one_goal.isChecked() else 'all'
        path=self.data_path
        self.busy=True
        for control in [self.start_button,self.file_button,self.reload_button,*self.mode_buttons.values()]:control.setEnabled(False)
        self.status.setText('Loading roster data…')
        def work():
            try:
                rows=read_csv(path)
                session=None
                if play:
                    session=(make_allstar_session(read_allstars(allstars_path()),start,end,season_rows=rows)
                             if mode=='all-stars' else make_session(select_range(rows,start,end),mode,team,goal,
                                  career_rows=rows,exclude_boundary_careers=True))
                self.events.put(('ready',(rows,session)))
            except Exception as error:self.events.put(('error',str(error)))
        threading.Thread(target=work,daemon=True).start()

    def poll(self):
        try:
            while True:
                kind,payload=self.events.get_nowait()
                self.busy=False
                for control in [self.start_button,self.file_button,self.reload_button,*self.mode_buttons.values()]:control.setEnabled(True)
                if kind=='error':self.status.setText(payload);continue
                self.rows,session=payload
                self.player_names=NameIndex([r.player_name for r in self.rows]+([r.player_name for r in session.answers] if session else []))
                self.college_names=NameIndex(name for r in self.rows for name in college_names(r.college))
                selected=self.team.currentData()
                names={}
                for r in self.rows:names.setdefault(r.team_id,set()).add(r.team_name)
                self.team.clear();self.team.addItem('All teams',None)
                for tid,nameset in sorted(names.items(),key=lambda pair:sorted(pair[1])[0]):self.team.addItem(' / '.join(sorted(nameset))+f' ({tid})',tid)
                self.team.setCurrentIndex(max(0,self.team.findData(selected)))
                self.status.setText(f'{len(self.rows):,} roster records loaded · {self.data_path.name}')
                if session:self.show_game(session)
        except queue.Empty:pass

    def table(self,headers):
        table=WrapTable(0,len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        table.setWordWrap(True)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        table.verticalHeader().hide()
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setMinimumSectionSize(30)
        table.setMinimumHeight(130)
        return table

    def show_game(self,session):
        if self.game_page:
            self.stack.removeWidget(self.game_page);self.game_page.deleteLater()
        self.session=session
        self.game_page=QWidget()
        layout=QVBoxLayout(self.game_page);layout.setContentsMargins(25,20,25,20);layout.setSpacing(9)
        layout.addWidget(label('◉  COURTSIDE','brand'))
        layout.addWidget(label(session.prompt,'headline'))
        self.tables={}
        self.team_buttons={}
        self.progress=label('','muted')
        if session.mode=='all-stars':
            layout.addWidget(label('NBA teams, age and college describe that season. Multiple NBA teams indicate a trade; selected injured players and replacements are included.','muted'))
            panels=QHBoxLayout()
            for conference in ('East','West'):
                column=QVBoxLayout();column.addWidget(label(conference.upper()+' ALL-STARS','brand'))
                table=self.table(['PLAYER','NBA TEAM(S)','AGE','COLLEGE'])
                table.horizontalHeader().setSectionResizeMode(2,QHeaderView.ResizeMode.Fixed);table.setColumnWidth(2,42)
                column.addWidget(table);panels.addLayout(column,1);self.tables[conference]=table
            layout.addLayout(panels,1)
        elif session.mode=='one-player':
            self.tables['roster']=self.table(['PLAYER','POS','GAMES','TRADED','JERSEY','HEIGHT','PPG','COLLEGE','AGE'])
            layout.addWidget(self.tables['roster'],1)
        elif session.mode=='college':
            layout.addWidget(label(f'{session.anchor.team_name} · {session.anchor.season} · Career {session.career_mpg:.1f} MPG / {session.career_minutes:,.0f} minutes','muted'))
            self.tables['college']=self.table(['COLLEGE']);layout.addWidget(self.tables['college'],1)
        else:
            stats=session.season_stats()
            layout.addWidget(label(f"{stats['games']} games · {stats['minutes_total']:,.0f} minutes · Approximate rates: "+' · '.join(f'{k.upper()} {v if v is not None else "—"}' for k,v in stats.items() if k in ('ppg','rpg','apg','spg','bpg')),'muted'))
            self.tables['teams']=self.table(['TEAM','GAMES']);self.tables['teams'].setMaximumHeight(140);layout.addWidget(self.tables['teams'])
            grid=QGridLayout()
            for i,(tid,name) in enumerate(session.team_options):
                control=button(name,lambda checked=False,t=tid:self.submit(t));control.setMinimumHeight(30)
                grid.addWidget(control,i//5,i%5);self.team_buttons[tid]=control
            for i in range(5):grid.setColumnStretch(i,1)
            layout.addLayout(grid,1)
        layout.addWidget(self.progress)
        self.entry=None;self.submit_button=None;self.hint_button=None
        if session.mode!='player-teams':
            row=QHBoxLayout()
            self.entry=CompletionInput()
            self.entry.index=self.college_names if session.mode=='college' else self.player_names
            self.entry.setPlaceholderText('College name…' if session.mode=='college' else 'Player name…')
            self.entry.returnPressed.connect(self.enter_guess)
            row.addWidget(self.entry,1)
            self.submit_button=button('Submit guess',self.submit,True);row.addWidget(self.submit_button)
            layout.addLayout(row)
        self.feedback=label();self.feedback.setMinimumHeight(38);layout.addWidget(self.feedback)
        actions=QHBoxLayout()
        if session.mode=='one-player':
            self.hint_button=button('Reveal all hints',self.hint);actions.addWidget(self.hint_button)
        self.quit_button=button('Quit & reveal answers',self.quit_game);actions.addWidget(self.quit_button)
        self.back_button=button('Return to menu',self.back,True);self.back_button.hide();actions.addWidget(self.back_button)
        actions.addStretch();layout.addLayout(actions)
        if session.mode=='one-player':layout.addWidget(label('★ Light-gold row = All-Star in this season. Unguessed revealed names appear red.','muted'))
        self.stack.addWidget(self.game_page);self.stack.setCurrentWidget(self.game_page)
        self.refresh()
        if self.entry:self.entry.setFocus()

    def enter_guess(self):
        if self.entry and not self.entry.skip_return and not self.entry.completion.popup().isVisible():self.submit()

    @staticmethod
    def text(value):return '—' if value is None or value=='' else str(value)

    def populate(self,table,rows):
        # Rows contain (values, was_guessed, is_star, reveal, needs_icon).
        table.setUpdatesEnabled(False)
        table.setRowCount(len(rows))
        for i,(values,found,star,reveal,icon) in enumerate(rows):
            for j,value in enumerate(values):
                item=QTableWidgetItem(self.text(value))
                if star:item.setBackground(QColor(GOLD))
                if reveal and not found:item.setForeground(QColor(RED))
                if icon and j==0:item.setIcon(self.icon)
                table.setItem(i,j,item)
        table.resizeRowsToContents()
        table.setUpdatesEnabled(True)

    def refresh(self):
        s=self.session;reveal=bool(s.outcome)
        if s.mode=='all-stars':
            counts=[]
            for conference,table in self.tables.items():
                roster=[r for r in s.answers if r.team_id==conference]
                values=[]
                for row in roster:
                    found=row.player_id in s.found
                    details=s.all_star_details.get(row.player_id,{})
                    values.append(([row.player_name if reveal or found else '________________',details.get('teams','—'),details.get('age','—'),details.get('college','—')],found,False,reveal,False))
                self.populate(table,values)
                counts.append(f'{conference}: {sum(r.player_id in s.found for r in roster)}/{len(roster)}')
            self.progress.setText('   ·   '.join(counts));return
        values=[]
        for row in s.answers:
            found=s.identity(row) in s.found
            visible=reveal or found
            if s.mode=='college':fields=[s.label(row) if visible else '________________']
            elif s.mode=='player-teams':fields=[row.team_name if visible else '________________',row.games]
            else:
                extras=[]
                for field in s.hint_fields:
                    value=getattr(row,field)
                    if field=='height_inches' and value is not None:value=f'{value//12}′ {value%12}″'
                    extras.append(value if visible or field in s.revealed_hints else 'Hidden')
                fields=[row.player_name if visible else '________________',row.position,row.games,'Yes' if len(s.traded.get((row.player_id,row.season_end),set()))>1 else 'No',*extras]
            star=s.mode=='one-player' and row.is_all_star==1
            values.append((fields,found,star,reveal,star))
        self.populate(next(iter(self.tables.values())),values)
        self.progress.setText(f'Found {len(s.found)} / {len(s.answers)}'+(f' · Incorrect {s.wrong}/5' if s.mode=='player-teams' else ''))

    def submit(self,team=None):
        if self.session.outcome:return
        if isinstance(team,bool):team=None
        value=team if team is not None else self.entry.text()
        if self.entry:self.entry.completion.popup().hide()
        message=self.session.guess(value)
        self.feedback.setText(message)
        if team is not None:
            control=self.team_buttons[team];control.setEnabled(False)
            control.setProperty('result','correct' if team in self.session.found else 'wrong')
            control.style().unpolish(control);control.style().polish(control)
        elif message=='Correct!':self.entry.clear()
        self.refresh()
        if self.session.outcome:self.finish()

    def hint(self):
        self.session.hint();self.refresh();self.hint_button.setText('Hints revealed');self.hint_button.setEnabled(False)

    def quit_game(self):self.session.quit();self.refresh();self.finish()

    def finish(self):
        for control in [self.entry,self.submit_button,self.hint_button,*self.team_buttons.values()]:
            if control:control.setEnabled(False)
        self.quit_button.setEnabled(False)
        self.back_button.show()
        self.feedback.setText({'victory':'Victory! You know your roster.','quit':'Answers revealed in red.','failure':'Game over — five incorrect guesses.'}[self.session.outcome])

    def back(self):self.stack.setCurrentWidget(self.menu_page)

    def resizeEvent(self,event):
        super().resizeEvent(event)
        if self.game_page:
            for table in self.tables.values():table.resizeRowsToContents()


def main():
    app=QApplication.instance() or QApplication(sys.argv)
    app.setStyle('Fusion')
    window=TriviaWindow()
    window.show()
    sys.exit(app.exec())


if __name__=='__main__':main()
