#!/usr/bin/env python3
"""
GUI for generating Prover9 Mafia scenarios.

Usage:
  python3 scripts/gui_generator.py

Features:
- Choose number of players.
- Auto-assign counts for mafia/doctor/cop based on player count (editable).
- Generate a Prover9 `.in` file in `prover9/` and open it in the default editor.

This uses `scripts/generate_prover9.py`'s `write_in` function to produce the file.
"""

import os
import string
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter import font as tkfont
from datetime import datetime
from tkinter import filedialog
from pathlib import Path
import sys
import tempfile
import json

# Ensure repository root is on sys.path so `import scripts.*` works when running
# the script from the repository root or elsewhere.
repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

try:
    import scripts.mace4_query as mq
except Exception:
    mq = None

# import the generator function
try:
    from scripts.generate_prover9 import write_in
except Exception as e:
    write_in = None
    IMPORT_ERROR = e
else:
    IMPORT_ERROR = None


def default_role_counts(n):
    # simple heuristic: 1 mafia per 4 players, at least 1; 1 doctor, 1 cop if enough players
    mafia = max(1, n // 4)
    doctor = 1 if n >= 4 else 0
    cop = 1 if n >= 5 else 0
    return mafia, doctor, cop


class GeneratorGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Mafia Prover9 generator')
        # start with a larger window and allow resizing so the UI is easier to use
        self.geometry('1000x700')
        self.minsize(700, 500)
        self.resizable(True, True)

        if IMPORT_ERROR:
            messagebox.showerror('Import error', f'Could not import generator module:\n{IMPORT_ERROR}')
            self.destroy()
            return

        # Make the main content scrollable: create a container with a Canvas
        # and a vertical Scrollbar, then place a Frame inside the Canvas.
        # We keep the name `frame` for the inner frame so the rest of the
        # file can continue using `frame` unchanged.
        container = ttk.Frame(self)
        container.grid(row=0, column=0, sticky='nsew')

        # allow the root window to expand the container when resized
        try:
            self.grid_rowconfigure(0, weight=1)
            self.grid_columnconfigure(0, weight=1)
        except Exception:
            pass

        canvas = tk.Canvas(container, borderwidth=0, highlightthickness=0)
        vsb = ttk.Scrollbar(container, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)

        vsb.grid(row=0, column=1, sticky='ns')
        canvas.grid(row=0, column=0, sticky='nsew')

        # allow canvas to expand if container expands
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        # inner frame that holds all widgets
        frame = ttk.Frame(canvas, padding=12)
        canvas.create_window((0, 0), window=frame, anchor='nw')

        # update scrollregion when the inner frame changes size
        def _on_frame_configure(event):
            try:
                canvas.configure(scrollregion=canvas.bbox("all"))
            except Exception:
                pass

        frame.bind('<Configure>', _on_frame_configure)

        # mousewheel support (basic): works on macOS/Windows (event.delta)
        def _on_mousewheel(event):
            # Normalize delta (event.delta is multiple of 120 on many systems)
            try:
                delta = int(-1 * (event.delta // 120))
            except Exception:
                # fallback for unusual delta values
                delta = -1 if getattr(event, 'delta', 0) > 0 else 1
            canvas.yview_scroll(delta, 'units')

        # bind to the canvas so wheel anywhere scrolls
        canvas.bind_all('<MouseWheel>', _on_mousewheel)

        # number of players
        ttk.Label(frame, text='Number of players:').grid(row=0, column=0, sticky='w')
        self.players_var = tk.IntVar(value=6)
        self.players_spin = ttk.Spinbox(frame, from_=4, to=20, textvariable=self.players_var, width=5, command=self.on_players_change)
        self.players_spin.grid(row=0, column=1, sticky='w')

    # (auto-assign roles is always enabled by design; checkbox removed)

        # role counts
        ttk.Label(frame, text='Mafia:').grid(row=2, column=0, sticky='w')
        self.mafia_var = tk.IntVar(value=1)
        self.mafia_spin = ttk.Spinbox(frame, from_=0, to=10, textvariable=self.mafia_var, width=5)
        self.mafia_spin.grid(row=2, column=1, sticky='w')

        ttk.Label(frame, text='Doctor:').grid(row=3, column=0, sticky='w')
        self.doc_var = tk.IntVar(value=1)
        self.doc_spin = ttk.Spinbox(frame, from_=0, to=10, textvariable=self.doc_var, width=5)
        self.doc_spin.grid(row=3, column=1, sticky='w')

        ttk.Label(frame, text='Cop:').grid(row=4, column=0, sticky='w')
        self.cop_var = tk.IntVar(value=1)
        self.cop_spin = ttk.Spinbox(frame, from_=0, to=10, textvariable=self.cop_var, width=5)
        self.cop_spin.grid(row=4, column=1, sticky='w')

        # nights
        ttk.Label(frame, text='Nights to simulate:').grid(row=5, column=0, sticky='w')
        self.nights_var = tk.IntVar(value=2)
        self.nights_spin = ttk.Spinbox(frame, from_=1, to=10, textvariable=self.nights_var, width=5)
        self.nights_spin.grid(row=5, column=1, sticky='w')

        # generate button
        self.generate_btn = ttk.Button(frame, text='Generate .in file', command=self.on_generate)
        self.generate_btn.grid(row=6, column=0, columnspan=2, pady=(10,0))

        # Model check UI
        ttk.Separator(frame, orient='horizontal').grid(row=8, column=0, columnspan=2, sticky='ew', pady=(8,8))
        ttk.Label(frame, text='Model check (.in file):').grid(row=9, column=0, sticky='w')
        self.file_var = tk.StringVar(value='')
        self.file_entry = ttk.Entry(frame, textvariable=self.file_var, width=30)
        self.file_entry.grid(row=9, column=1, sticky='w')
        self.browse_btn = ttk.Button(frame, text='Browse', command=self.browse_file)
        self.browse_btn.grid(row=9, column=2, sticky='w')

        ttk.Label(frame, text='Player (a):').grid(row=10, column=0, sticky='w')
        self.player_var = tk.StringVar(value='a')
        self.player_spin = ttk.Spinbox(frame, values=list(string.ascii_lowercase), textvariable=self.player_var, width=5)
        self.player_spin.grid(row=10, column=1, sticky='w')

        ttk.Label(frame, text='Time:').grid(row=11, column=0, sticky='w')
        self.time_var = tk.StringVar(value='n1')
        # time combobox will be populated after scenario generation (n0..nN)
        self.time_cb = ttk.Combobox(frame, textvariable=self.time_var, values=['n0','n1'], width=8)
        self.time_cb.grid(row=11, column=1, sticky='w')

        # Check alive button: runs a Mace4 model-finder query to see if a model
        # exists with alive(player,time). We provide a small help button next to
        # it so users can read what this does without digging into docs.
        self.check_btn = ttk.Button(frame, text='Check alive (Mace4)', command=self.on_check_alive)
        self.check_btn.grid(row=12, column=0, columnspan=1, pady=(6,0), sticky='w')
        # little help button with a concise explanation
        self.check_help_btn = ttk.Button(frame, text='?', width=2, command=self.show_check_help)
        self.check_help_btn.grid(row=12, column=1, sticky='w', padx=(6,0))
        self.check_status = ttk.Label(frame, text='')
        self.check_status.grid(row=13, column=0, columnspan=3, sticky='w')

    # (removed Max domain UI - Mace4 domain bounding removed from GUI)

        # status
        self.status = ttk.Label(frame, text='')
        self.status.grid(row=7, column=0, columnspan=2, sticky='w')
        # Night control UI
        night_frame = ttk.LabelFrame(frame, text='Night controls', padding=8)
        night_frame.grid(row=15, column=0, columnspan=3, sticky='ew', pady=(8,0))

        ttk.Label(night_frame, text='Mafia target:').grid(row=0, column=0, sticky='w')
        self.mafia_target_var = tk.StringVar(value='')
        self.mafia_target_cb = ttk.Combobox(night_frame, textvariable=self.mafia_target_var, values=[], width=6)
        self.mafia_target_cb.grid(row=0, column=1, sticky='w')

        ttk.Label(night_frame, text='Doctor target:').grid(row=1, column=0, sticky='w')
        self.doc_target_var = tk.StringVar(value='')
        self.doc_target_cb = ttk.Combobox(night_frame, textvariable=self.doc_target_var, values=[], width=6)
        self.doc_target_cb.grid(row=1, column=1, sticky='w')

        ttk.Label(night_frame, text='Cop investigate:').grid(row=2, column=0, sticky='w')
        self.cop_target_var = tk.StringVar(value='')
        self.cop_target_cb = ttk.Combobox(night_frame, textvariable=self.cop_target_var, values=[], width=6)
        self.cop_target_cb.grid(row=2, column=1, sticky='w')

        self.next_btn = ttk.Button(night_frame, text='Next night', command=self.on_next_night)
        self.next_btn.grid(row=3, column=0, pady=(6,0))

        # Player status list
        status_frame = ttk.LabelFrame(frame, text='Players', padding=6)
        status_frame.grid(row=16, column=0, columnspan=3, sticky='ew', pady=(8,0))
        self.player_list = tk.Listbox(status_frame, height=8, width=30)
        self.player_list.grid(row=0, column=0, sticky='w')
        self.refresh_player_cb = ttk.Button(status_frame, text='Refresh players', command=self.refresh_player_list)
        self.refresh_player_cb.grid(row=0, column=1, sticky='n')

        # fonts for list styling (normal and struck-through for eliminated)
        try:
            base = tkfont.nametofont("TkDefaultFont")
            self._player_font = base.copy()
            self._player_strike = base.copy()
            self._player_strike.configure(overstrike=1)
        except Exception:
            self._player_font = None
            self._player_strike = None

        # Suggest player combobox (so user can pick without list selection)
        ttk.Label(status_frame, text='Suggest player:').grid(row=1, column=0, sticky='w')
        self.suggest_player_var = tk.StringVar(value='')
        self.suggest_player_cb = ttk.Combobox(status_frame, textvariable=self.suggest_player_var, values=[], width=6)
        self.suggest_player_cb.grid(row=1, column=1, sticky='w')
        # Move Suggest button next to the suggest-player combobox for convenience
        self.suggest_btn = ttk.Button(status_frame, text='Suggest moves', command=self.on_suggest)
        self.suggest_btn.grid(row=1, column=2, padx=(6,0))

        # internal game state for stepping nights
        self.scenario = None
        self.current_night = 0
        self.alive_set = set()

        # Day voting UI
        day_frame = ttk.LabelFrame(frame, text='Day / Voting', padding=6)
        day_frame.grid(row=17, column=0, columnspan=3, sticky='ew', pady=(8,0))
        ttk.Label(day_frame, text='Voter:').grid(row=0, column=0, sticky='w')
        self.voter_var = tk.StringVar(value='')
        self.voter_cb = ttk.Combobox(day_frame, textvariable=self.voter_var, values=[], width=6)
        self.voter_cb.grid(row=0, column=1, sticky='w')

        ttk.Label(day_frame, text='Vote target:').grid(row=0, column=2, sticky='w')
        self.vote_target_var = tk.StringVar(value='')
        self.vote_target_cb = ttk.Combobox(day_frame, textvariable=self.vote_target_var, values=[], width=6)
        self.vote_target_cb.grid(row=0, column=3, sticky='w')

        self.add_vote_btn = ttk.Button(day_frame, text='Add vote', command=self.on_add_vote)
        self.add_vote_btn.grid(row=0, column=4, padx=(6,0))

        self.votes_list = tk.Listbox(day_frame, height=6, width=40)
        self.votes_list.grid(row=1, column=0, columnspan=4, sticky='w')
        self.tally_btn = ttk.Button(day_frame, text='Tally votes', command=self.on_tally_votes)
        self.tally_btn.grid(row=1, column=4, padx=(6,0))

        # track votes in-memory for the current day index
        self._current_day_votes = []
        # cop reveal label
        self.cop_reveal_lbl = ttk.Label(day_frame, text='')
        self.cop_reveal_lbl.grid(row=2, column=0, columnspan=5, sticky='w', pady=(6,0))

        # initialize auto assignment
        self.on_players_change()

    def on_players_change(self):
        n = self.players_var.get()
        # auto-assign is always active: compute defaults from player count
        mafia, doc, cop = default_role_counts(n)
        # ensure sum <= n
        if mafia + doc + cop > n:
            # adjust mafia down
            mafia = max(1, n - doc - cop)
        self.mafia_var.set(mafia)
        self.doc_var.set(doc)
        self.cop_var.set(cop)
        # refresh vote controls if present
        try:
            self.refresh_vote_controls()
        except Exception:
            pass

    # auto-assign is always active; no toggle handler required

    def on_generate(self):
        n = self.players_var.get()
        mafia = self.mafia_var.get()
        doc = self.doc_var.get()
        cop = self.cop_var.get()
        nights = self.nights_var.get()

        if mafia < 1:
            messagebox.showerror('Validation error', 'There must be at least 1 mafia.')
            return
        if mafia + doc + cop > n:
            messagebox.showerror('Validation error', 'Sum of special roles exceeds number of players.')
            return

        # assign player names a,b,c,...
        players = list(string.ascii_lowercase[:n])
        roles = {}
        assigned = set()

        # assign mafia(s)
        for i in range(mafia):
            roles[players[i]] = 'mafia'
            assigned.add(players[i])
        idx = mafia
        if doc > 0:
            roles[players[idx]] = 'doctor'
            assigned.add(players[idx])
            idx += 1
        if cop > 0:
            roles[players[idx]] = 'cop'
            assigned.add(players[idx])
            idx += 1
        # rest villagers
        for p in players:
            if p not in assigned:
                roles[p] = 'villager'

        # build scenario dict with empty actions and votes (user can edit .in later)
        scenario = {
            'players': players,
            'roles': roles,
            'nights': nights,
            'night_actions': {},
            'day_votes': {}
        }

        # create output path
        safe_time = datetime.now().strftime('%Y%m%d_%H%M%S')
        out_name = f'gui_generated_{safe_time}.in'
        out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'prover9', out_name))
        os.makedirs(os.path.dirname(out_path), exist_ok=True)

        try:
            write_in(out_path, scenario)
        except Exception as e:
            messagebox.showerror('Generation error', f'Failed to write file:\n{e}')
            return

        # open file in default editor (macOS open)
        try:
            os.system(f'open "{out_path}"')
        except Exception:
            pass
        # set the generated file path in the Model check field so user can immediately check it
        self.file_var.set(out_path)

        messagebox.showinfo('Done', f'Wrote {out_path}')
        self.status.config(text=f'Wrote {out_path}')
        # initialize internal scenario state for stepping
        self.scenario = scenario
        self.current_night = 0
        self.alive_set = set(players)
        # populate target comboboxes
        vals = players.copy()
        self.mafia_target_cb['values'] = vals
        self.doc_target_cb['values'] = vals
        self.cop_target_cb['values'] = vals
        # populate suggest-player combobox
        self.suggest_player_cb['values'] = vals
        # populate time combobox n0..nN
        times = [f'n{i}' for i in range(0, nights + 1)]
        self.time_cb['values'] = times
        # default to n1 if available
        if 'n1' in times:
            self.time_var.set('n1')
        else:
            self.time_var.set(times[0] if times else '')
        # refresh player list display
        self.refresh_player_list()
        # ensure night controls are enabled for a new scenario
        try:
            self.next_btn.state(['!disabled'])
            self.suggest_btn.state(['!disabled'])
            self.mafia_target_cb.state(['!enabled'])
            self.doc_target_cb.state(['!enabled'])
            self.cop_target_cb.state(['!enabled'])
        except Exception:
            pass

    def browse_file(self):
        p = filedialog.askopenfilename(initialdir=os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'prover9')), filetypes=[('Prover9 files', '*.in'), ('All files', '*')])
        if p:
            self.file_var.set(p)

    def refresh_player_list(self):
        self.player_list.delete(0, 'end')
        if not self.scenario:
            # show players placeholder from current spinner
            try:
                n = self.players_var.get()
                players = list(string.ascii_lowercase[:n])
            except Exception:
                players = []
            for p in players:
                self.player_list.insert('end', f'{p}: unknown')
            # also update suggest player combobox values to match placeholder
            try:
                self.suggest_player_cb['values'] = players
            except Exception:
                pass
            return
        for p in self.scenario.get('players', []):
            status = 'alive' if p in self.alive_set else 'dead'
            role = self.scenario.get('roles', {}).get(p, '?')
            self.player_list.insert('end', f'{p}: {status} ({role})')
            # style eliminated players with strike-through / gray
            try:
                idx = self.player_list.size() - 1
                if status == 'dead':
                    if self._player_strike is not None:
                        self.player_list.itemconfig(idx, foreground='gray40', font=self._player_strike)
                    else:
                        self.player_list.itemconfig(idx, foreground='gray40')
                else:
                    if self._player_font is not None:
                        self.player_list.itemconfig(idx, font=self._player_font, foreground='black')
            except Exception:
                pass
        # update suggest-player combobox to current players (alive first)
        try:
            vals = [p for p in self.scenario.get('players', []) if p in self.alive_set]
            if not vals:
                vals = self.scenario.get('players', [])
            self.suggest_player_cb['values'] = vals
            # also refresh voter/target comboboxes
            try:
                self.voter_cb['values'] = vals
                self.vote_target_cb['values'] = vals
                # refresh votes list display
                self.refresh_vote_controls()
            except Exception:
                pass
        except Exception:
            pass

    def show_check_help(self):
        """Show a short, user-friendly explanation of what "Check alive" does.

        Keep it simple: explain that this runs the finite-model finder (Mace4)
        on the generated `.in` file to see whether there exists a model where
        the predicate alive(player,time) holds. If Mace4 is not available the
        feature can't run and the user will see a friendly message.
        """
        msg = (
            "Check alive (what it does):\n\n"
            "This runs the finite-model search (Mace4) on the .in file you selected.\n"
            "It asks: 'Is there any model where alive(<player>,<time>) is true?'\n\n"
            "Interpretation: if a model is found, the solver found a consistent\n"
            "scenario where that player is alive at that time. If no model is\n"
            "found, the property is unsatisfiable (or the parser couldn't read\n"
            "the solver output).\n\n"
            "Notes: This is an automated logical search -- it does not assert\n"
            "the actual game state, but whether such a state is consistent\n"
            "with the rules encoded in the .in file. Use the generated .in\n"
            "file to inspect or tweak the axioms if results look surprising."
        )
        messagebox.showinfo('Check alive — help', msg)

    def check_win(self):
        """Check current alive set for a win condition.

        Rules used:
        - Villagers win if no mafia are alive.
        - Mafia win if number of alive mafia >= number of alive non-mafia players.
        Returns: 'villagers', 'mafia', or None
        """
        if not self.scenario:
            return None
        alive = set(self.alive_set)
        if not alive:
            return None
        roles = self.scenario.get('roles', {})
        mafia_alive = sum(1 for p in alive if roles.get(p) == 'mafia')
        others_alive = sum(1 for p in alive if roles.get(p) != 'mafia')

        if mafia_alive == 0:
            return 'villagers'
        if mafia_alive >= others_alive:
            return 'mafia'
        return None

    def on_next_night(self):
        # apply selected actions for current night and advance
        if not self.scenario:
            messagebox.showerror('No scenario', 'Generate or load a scenario first.')
            return
        n = self.current_night
        acts = []
        m_target = self.mafia_target_var.get().strip()
        d_target = self.doc_target_var.get().strip()
        c_target = self.cop_target_var.get().strip()
        if m_target:
            acts.append({'type': 'kill', 'by': 'mafia', 'target': m_target})
        if d_target:
            acts.append({'type': 'protect', 'by': 'doctor', 'target': d_target})
        if c_target:
            acts.append({'type': 'investigate', 'by': 'cop', 'target': c_target})
        # record actions under night_actions
        self.scenario.setdefault('night_actions', {})[str(n)] = []
        # generator expects 'by' to be a player constant; our GUI uses roles, try map
        # map role names to actual players if unique, else use first player with that role
        role_map = {}
        for p, r in self.scenario.get('roles', {}).items():
            role_map.setdefault(r, []).append(p)
        recorded = []
        for a in acts:
            typ = a['type']
            by = a['by']
            target = a['target']
            if by in ('mafia', 'doctor', 'cop'):
                by_list = role_map.get(by, [])
                by_actor = by_list[0] if by_list else by
            else:
                by_actor = by
            # Prevent a killer from killing themselves
            if typ == 'kill' and by_actor == target:
                messagebox.showerror('Invalid action', 'A killer cannot kill themselves. Change the Mafia target.')
                return
            recorded.append({'type': typ, 'by': by_actor, 'target': target})
        self.scenario['night_actions'][str(n)] = recorded

        # simulate outcome locally: if mafia targeted someone and doctor did not protect same person -> death
        if m_target and (m_target != d_target) and (m_target in self.alive_set):
            self.alive_set.discard(m_target)

        # advance night
        self.current_night += 1

        # write updated .in file with current scenario
        try:
            # write to same out path as file_var if set, else to prover9/gui_generated_next.in
            outp = self.file_var.get().strip() or os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'prover9', f'gui_generated_step_{datetime.now().strftime("%Y%m%d_%H%M%S")}.in'))
            write_in(outp, self.scenario)
            self.file_var.set(outp)
        except Exception as e:
            messagebox.showerror('Write error', f'Failed to write updated .in: {e}')

        # update combobox options to current alive players
        vals = [p for p in self.scenario.get('players', []) if p in self.alive_set]
        if not vals:
            vals = self.scenario.get('players', [])
        self.mafia_target_cb['values'] = vals
        self.doc_target_cb['values'] = vals
        self.cop_target_cb['values'] = vals

        self.refresh_player_list()

        # reset current day votes for the new day
        self._current_day_votes = []
        try:
            self.refresh_vote_controls()
        except Exception:
            pass

        # check for win condition
        winner = self.check_win()
        if winner:
            if winner == 'villagers':
                message = 'Villagers win! All Mafia have been eliminated.'
            else:
                message = 'Mafia win! Mafia control the town or are tied with town.'
            messagebox.showinfo('Game Over', message)
            self.status.config(text=message)
            # disable night controls to prevent further play
            try:
                self.next_btn.state(['disabled'])
                self.suggest_btn.state(['disabled'])
                self.mafia_target_cb.state(['disabled'])
                self.doc_target_cb.state(['disabled'])
                self.cop_target_cb.state(['disabled'])
            except Exception:
                pass

    def on_suggest(self):
        # Suggest role-aware moves for the selected player (use suggest combo first, then list)
        sel = self.suggest_player_var.get().strip() if hasattr(self, 'suggest_player_var') else ''
        if not sel:
            try:
                sel_idx = self.player_list.curselection()
                if sel_idx:
                    sel = self.player_list.get(sel_idx[0]).split(':')[0]
            except Exception:
                sel = None
        if not sel:
            messagebox.showinfo('Suggest', 'Select a player (using the Suggest player box or the Players list) to get suggestions.')
            return

        if not self.scenario:
            messagebox.showinfo('Suggest', 'Generate or load a scenario first.')
            return

        role = self.scenario.get('roles', {}).get(sel, 'villager')
        suggestions = []
        next_time = f'n{self.current_night+1}'
        maxd = None

        # helper to run a simulated action and check a Mace4 query
        def simulate_and_check(temp_scn, query):
            tmp = None
            try:
                with tempfile.NamedTemporaryFile('w', suffix='.in', delete=False) as tf:
                    tmp = tf.name
                    try:
                        write_in(tmp, temp_scn)
                    except Exception:
                        pass
                rc, out, parsed = mq.run_query_return(Path(tmp), query) if mq is not None else (-2, '', {})
            except Exception as e:
                return -1, str(e), {}
            finally:
                # cleanup temp file
                try:
                    if tmp and os.path.exists(tmp):
                        os.unlink(tmp)
                except Exception:
                    pass
            return rc, out, parsed

        # Role-specific heuristics
        if role == 'doctor':
            suggestions.append('You are a Doctor — protect someone tonight to save them.')
            # try protecting each alive player (including self)
            for tgt in [p for p in self.scenario.get('players', []) if p in self.alive_set]:
                temp = json.loads(json.dumps(self.scenario))
                temp.setdefault('night_actions', {})[str(self.current_night)] = []
                temp['night_actions'][str(self.current_night)].append({'type': 'protect', 'by': sel, 'target': tgt})
                if mq is not None:
                    rc, out, parsed = simulate_and_check(temp, f'alive({tgt},{next_time})')
                    if rc == 0 and parsed:
                        suggestions.append(f'Verified: protecting {tgt} can produce a model where they survive.')
                    else:
                        suggestions.append(f'Check failed/unknown for protecting {tgt}.')

        elif role == 'mafia':
            suggestions.append('You are Mafia — choose a kill target to reduce town power.')
            # prefer killing cops/doctors first
            candidates = [p for p in self.scenario.get('players', []) if p in self.alive_set and p != sel]
            # sort by priority: cop, doctor, villager
            def priority(p):
                r = self.scenario.get('roles', {}).get(p, 'villager')
                return 0 if r == 'cop' else (1 if r == 'doctor' else 2)
            candidates.sort(key=priority)
            # compute alive cops before simulating; used to detect killing last cop
            cops_alive = [p for p, r in self.scenario.get('roles', {}).items() if r == 'cop' and p in self.alive_set]
            # compute alive cops before simulating; used to detect killing last cop
            cops_alive = [p for p, r in self.scenario.get('roles', {}).items() if r == 'cop' and p in self.alive_set]
            doctors_alive = [p for p, r in self.scenario.get('roles', {}).items() if r == 'doctor' and p in self.alive_set]
            for tgt in candidates:
                temp = json.loads(json.dumps(self.scenario))
                temp.setdefault('night_actions', {})[str(self.current_night)] = []
                temp['night_actions'][str(self.current_night)].append({'type': 'kill', 'by': sel, 'target': tgt})
                # heuristic warnings
                tgt_role = self.scenario.get('roles', {}).get(tgt, 'villager')
                if tgt_role == 'cop':
                    # if this is the last alive cop, killing them is a huge advantage for mafia
                    if len(cops_alive) == 1 and tgt in cops_alive:
                        suggestions.append(f'Killing {tgt} would eliminate the last Cop — this may allow the Mafia to win.')
                    else:
                        suggestions.append(f'Killing {tgt} (Cop) weakens the town.')
                if tgt_role == 'doctor':
                    # killing the last doctor removes protection ability — big advantage
                    if len(doctors_alive) == 1 and tgt in doctors_alive:
                        suggestions.append(f'Killing {tgt} would eliminate the last Doctor — no more protections possible, increasing Mafia chances.')
                    else:
                        suggestions.append(f'Killing {tgt} (Doctor) reduces town protection capability.')
                if mq is not None:
                    # check if there is a model where target is dead next_time
                    rc, out, parsed = simulate_and_check(temp, f'-alive({tgt},{next_time})')
                    if rc == 0 and parsed:
                        suggestions.append(f'Verified kill possible: killing {tgt} can lead to them being dead at {next_time}.')
                    else:
                        suggestions.append(f'Could not verify kill-for-{tgt} (unknown/unsat).')

        elif role == 'cop':
            suggestions.append('You are a Cop — investigate someone to reveal their alignment.')
            candidates = [p for p in self.scenario.get('players', []) if p in self.alive_set and p != sel]
            for tgt in candidates:
                suggestions.append(f'Investigate {tgt} (heuristic).')
                # if target is mafia in the scenario, investigating them yields town win
                tgt_role = self.scenario.get('roles', {}).get(tgt, 'villager')
                if tgt_role == 'mafia':
                    suggestions.append(f'If you investigate {tgt} you will find they are MAFIA — Villagers can win.')
                if mq is not None:
                    temp = json.loads(json.dumps(self.scenario))
                    temp.setdefault('night_actions', {})[str(self.current_night)] = []
                    temp['night_actions'][str(self.current_night)].append({'type': 'investigate', 'by': sel, 'target': tgt})
                    rc, out, parsed = simulate_and_check(temp, f'investigate({sel},{tgt},n{self.current_night})')
                    if rc == 0 and parsed:
                        suggestions.append(f'Investigation action for {tgt} is consistent in a model (parser OK).')

        else:
            # villager or unknown
            suggestions.append('You are a Villager — try to get protected or follow Cop leads when available.')
            # if there's a doctor, suggest asking doctor to protect you
            doc_player = next((p for p, r in self.scenario.get('roles', {}).items() if r == 'doctor'), None)
            if doc_player:
                temp = json.loads(json.dumps(self.scenario))
                temp.setdefault('night_actions', {})[str(self.current_night)] = []
                temp['night_actions'][str(self.current_night)].append({'type': 'protect', 'by': doc_player, 'target': sel})
                if mq is not None:
                    rc, out, parsed = simulate_and_check(temp, f'alive({sel},{next_time})')
                    if rc == 0 and parsed:
                        suggestions.append(f'Verified: doctor protecting you can yield survival.')
                    else:
                        suggestions.append('Mace4 check: doctor-protect did NOT produce a model (unknown).')

        # present suggestions
        msg = '\n'.join(suggestions) if suggestions else 'No suggestions generated.'
        messagebox.showinfo('Suggestions for ' + sel, msg)

    def refresh_vote_controls(self):
        """Refresh vote comboboxes and votes list; show any cop reveals from previous night."""
        # populate comboboxes with alive players
        vals = []
        if self.scenario:
            vals = [p for p in self.scenario.get('players', []) if p in self.alive_set]
            if not vals:
                vals = list(self.scenario.get('players', []))
        try:
            # hide voters who have already voted this day (persisted or in-memory)
            day_idx = max(0, self.current_night - 1)
            persisted = [d.get('voter') for d in self.scenario.get('day_votes', {}).get(str(day_idx), [])] if self.scenario else []
            voted_now = [v for v, _ in self._current_day_votes]
            already = set(persisted + voted_now)
            available_voters = [p for p in vals if p not in already]
            self.voter_cb['values'] = available_voters
            # disable add button if no available voters
            if not available_voters:
                try:
                    self.add_vote_btn.state(['disabled'])
                except Exception:
                    pass
            else:
                try:
                    self.add_vote_btn.state(['!disabled'])
                except Exception:
                    pass
            self.vote_target_cb['values'] = vals
        except Exception:
            pass

        # populate votes list
        self.votes_list.delete(0, 'end')
        for v, t in self._current_day_votes:
            self.votes_list.insert('end', f'{v} -> {t}')

        # show cop reveals from last night (if any)
        reveal_msgs = []
        if self.scenario and self.current_night > 0:
            night_idx = str(self.current_night - 1)
            acts = self.scenario.get('night_actions', {}).get(night_idx, [])
            for a in acts:
                if a.get('type') == 'investigate':
                    by = a.get('by')
                    tgt = a.get('target')
                    # if the target is mafia, cop recognizes
                    if self.scenario.get('roles', {}).get(tgt) == 'mafia':
                        reveal_msgs.append(f'Cop {by} discovered mafia: {tgt}')
        self.cop_reveal_lbl.config(text='; '.join(reveal_msgs))

    def show_check_help(self):
        """Show a short, user-friendly explanation of what "Check alive" does.

        Keep it simple: explain that this runs the finite-model finder (Mace4)
        on the generated `.in` file to see whether there exists a model where
        the predicate alive(player,time) holds. If Mace4 is not available the
        feature can't run and the user will see a friendly message.
        """
        msg = (
            "Check alive (what it does):\n\n"
            "This runs the finite-model search (Mace4) on the .in file you selected.\n"
            "It asks: 'Is there any model where alive(<player>,<time>) is true?'\n\n"
            "Interpretation: if a model is found, the solver found a consistent\n"
            "scenario where that player is alive at that time. If no model is\n"
            "found, the property is unsatisfiable (or the parser couldn't read\n"
            "the solver output).\n\n"
            "Notes: This is an automated logical search -- it does not assert\n"
            "the actual game state, but whether such a state is consistent\n"
            "with the rules encoded in the .in file. Use the generated .in\n"
            "file to inspect or tweak the axioms if results look surprising."
        )
        messagebox.showinfo('Check alive — help', msg)

    def animate_elimination(self, player: str):
        """Simple flash animation for an eliminated player in the Listbox."""
        try:
            idx = None
            for i in range(self.player_list.size()):
                txt = self.player_list.get(i)
                if txt.startswith(f'{player}:'):
                    idx = i
                    break
            if idx is None:
                return
            default_bg = self.player_list.cget('background')

            def _flash(step=0):
                try:
                    if step % 2 == 0:
                        self.player_list.itemconfig(idx, background='yellow')
                    else:
                        self.player_list.itemconfig(idx, background=default_bg)
                except Exception:
                    pass
                if step < 5:
                    self.after(120, lambda: _flash(step + 1))

            _flash(0)
        except Exception:
            pass

    def on_add_vote(self):
        if not self.scenario:
            messagebox.showerror('No scenario', 'Generate or load a scenario first.')
            return
        voter = self.voter_var.get().strip()
        target = self.vote_target_var.get().strip()
        if not voter or not target:
            messagebox.showerror('Input error', 'Select both voter and target.')
            return
        # disallow voting for oneself
        if voter == target:
            messagebox.showerror('Invalid vote', 'You cannot vote for yourself.')
            return
        # disallow voting twice in the same day (check in-memory and persisted day_votes)
        day_idx = max(0, self.current_night - 1)
        existing_voters = [v for v, _ in self._current_day_votes]
        # include persisted votes for current day
        persisted = [d.get('voter') for d in self.scenario.get('day_votes', {}).get(str(day_idx), [])]
        existing_voters.extend(persisted)
        if voter in existing_voters:
            messagebox.showerror('Duplicate vote', f'{voter} has already voted this day.')
            return
        if voter not in self.alive_set:
            messagebox.showerror('Invalid voter', f'{voter} is not alive.')
            return
        if target not in self.alive_set:
            messagebox.showerror('Invalid target', f'{target} is not alive.')
            return

        # record vote in-memory
        self._current_day_votes.append((voter, target))
        self.votes_list.insert('end', f'{voter} -> {target}')

        # also append to scenario day_votes for persistence
        day_idx = max(0, self.current_night - 1)
        self.scenario.setdefault('day_votes', {}).setdefault(str(day_idx), []).append({'voter': voter, 'target': target})

    def on_tally_votes(self):
        if not self.scenario:
            messagebox.showerror('No scenario', 'Generate or load a scenario first.')
            return
        # compute counts from current day's votes in scenario (use stored day_votes)
        day_idx = max(0, self.current_night - 1)
        votes = list(self.scenario.get('day_votes', {}).get(str(day_idx), []))
        if not votes:
            messagebox.showinfo('Tally', 'No votes to tally for this day.')
            return
        from collections import Counter
        cnt = Counter([v['target'] for v in votes])
        most = cnt.most_common()
        top_count = most[0][1]
        top = [p for p, c in most if c == top_count]
        if len(top) == 1:
            eliminated = top[0]
            if eliminated in self.alive_set:
                self.alive_set.discard(eliminated)
            messagebox.showinfo('Tally', f'{eliminated} was eliminated by vote.')
            # write updated .in to reflect elimination
            try:
                outp = self.file_var.get().strip() or os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'prover9', f'gui_generated_step_{datetime.now().strftime("%Y%m%d_%H%M%S")}.in'))
                write_in(outp, self.scenario)
                self.file_var.set(outp)
            except Exception as e:
                messagebox.showerror('Write error', f'Failed to write updated .in: {e}')
            # refresh display immediately and check win condition
            self.refresh_player_list()
            try:
                self.refresh_vote_controls()
            except Exception:
                pass
            # animate elimination in the players list
            try:
                self.animate_elimination(eliminated)
            except Exception:
                pass
            # check for win condition after elimination
            winner = self.check_win()
            if winner:
                if winner == 'villagers':
                    msg = 'Villagers win! All Mafia have been eliminated.'
                else:
                    msg = 'Mafia win! Mafia control the town or are tied with town.'
                messagebox.showinfo('Game Over', msg)
                self.status.config(text=msg)
                # disable night controls to prevent further play
                try:
                    self.next_btn.state(['disabled'])
                    self.suggest_btn.state(['disabled'])
                    self.mafia_target_cb.state(['disabled'])
                    self.doc_target_cb.state(['disabled'])
                    self.cop_target_cb.state(['disabled'])
                except Exception:
                    pass
        else:
            messagebox.showinfo('Tally', 'No unique top vote; no one eliminated.')

        # refresh GUI
        self.refresh_player_list()
        try:
            self.refresh_vote_controls()
        except Exception:
            pass

    def on_check_alive(self):
        # Friendly behavior: if the Mace4 helper is not available, show an
        # explanatory info instead of a hard error. Otherwise run the query.
        if mq is None:
            messagebox.showinfo(
                'Mace4 not available',
                'The Mace4 helper module is not available in this environment.\n\n'
                'To use this feature, install Mace4 and ensure the helper\n'
                '`scripts/mace4_query.py` is present.\n\n'
                'You can still inspect the generated .in file manually (Browse) and\n'
                'run Mace4 externally if desired.'
            )
            self.check_status.config(text='Mace4 not available (see help)', foreground='orange')
            return

        f = self.file_var.get().strip()
        if not f:
            messagebox.showerror('No file', 'Select a .in file first (Browse).')
            return

        player = self.player_var.get().strip()
        time = self.time_var.get().strip()
        query = f"alive({player},{time})"

        # disable the check button/help while running to avoid duplicate runs
        try:
            self.check_btn.state(['disabled'])
            self.check_help_btn.state(['disabled'])
        except Exception:
            pass
        self.check_status.config(text='Running Mace4...', foreground='black')

        try:
            try:
                rc, out, parsed = mq.run_query_return(Path(f), query)
            except Exception as e:
                messagebox.showerror('Error', f'Failed to run Mace4 query:\n{e}')
                self.check_status.config(text='Mace4 error', foreground='red')
                return

            # Interpret parsed
            result = 'no model (unsat or error)'
            # if Mace4 returned non-zero, show its output to help debug
            if rc != 0:
                messagebox.showerror('Mace4 error', f'Mace4 exited with code {rc}. Output:\n\n{out}')
                self.check_status.config(text='Mace4 error (see popup)', foreground='red')
                return

            if not parsed:
                # rc == 0 but parser returned nothing -> likely UNSAT (no model) or parsing gap
                result = 'No model found (unsatisfiable) or parser failed.'
                if out:
                    preview = out if len(out) < 3000 else out[:3000] + '\n\n... (truncated)'
                    messagebox.showinfo('Mace4 output (preview)', preview)
                self.check_status.config(text=result, foreground='red')
                return

            # At this point we have a parsed model. Show the model summary
            # (if available) and set a friendly status. The detailed mapping
            # of constants to indices can be brittle, so we show the model and
            # a readable result rather than attempting a fragile index math.
            summary = mq.summarize_model(parsed) if hasattr(mq, 'summarize_model') else None
            if summary:
                # Show the model popup so users can inspect relations and domain
                self.show_model_popup(summary)
                self.check_status.config(text='Model found — see model summary', foreground='green')
            else:
                # No summarizer available; still report success
                self.check_status.config(text='Model found (parsed) — see output', foreground='green')

        finally:
            # re-enable buttons
            try:
                self.check_btn.state(['!disabled'])
                self.check_help_btn.state(['!disabled'])
            except Exception:
                pass

    def on_check_win(self):
        # Generate a JSON state from the current GUI state, save it and call the prover9 checker
        if not self.scenario:
            messagebox.showerror('No scenario', 'Generate or load a scenario first.')
            return

        # build state dict
        state = {
            'players': list(self.scenario.get('players', [])),
            'roles': dict(self.scenario.get('roles', {})),
            'alive': list(self.alive_set),
            'time': self.time_var.get().strip() or f'n{self.current_night}'
        }

        # write JSON state to a temp file (for user inspection if desired)
        tmp_json = None
        try:
            with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as jf:
                tmp_json = jf.name
                json.dump(state, jf, indent=2)
        except Exception:
            tmp_json = None

        # attempt to use the check_win helper if available
        try:
            import scripts.check_win_prover9 as cw
        except Exception:
            cw = None

        if cw is not None and hasattr(cw, 'check_state'):
            try:
                res = cw.check_state(state)
            except Exception as e:
                messagebox.showerror('Check error', f'Failed to run prover9 check: {e}')
                return
            # map results
            vill = res.get('villagers')
            mafi = res.get('mafia')
            msgs = []
            for q, (rc, sat) in res.get('results', {}).items():
                msgs.append(f"{q}: {'sat' if sat else 'unsat/unknown'} (rc={rc})")
            summary = '\n'.join(msgs)
            # show JSON path and results
            info_msg = f"State JSON: {tmp_json if tmp_json else '(not saved)'}\n\n{summary}"
            messagebox.showinfo('Prover9 win check', info_msg)

            # Update UI similar to local check
            if vill and not mafi:
                msg = 'Villagers win (Prover9 model found)'
            elif mafi and not vill:
                msg = 'Mafia win (Prover9 model found)'
            elif mafi and vill:
                msg = 'Both win predicates satisfiable (ambiguous)'
            else:
                msg = 'No winner yet (Prover9 did not find win predicate)'
            self.status.config(text=msg)
            # disable controls only when exactly one win predicate is true
            # (i.e., villagers XOR mafia). If both are true it's ambiguous; keep controls enabled.
            if bool(vill) ^ bool(mafi):
                try:
                    self.next_btn.state(['disabled'])
                    self.suggest_btn.state(['disabled'])
                    self.mafia_target_cb.state(['disabled'])
                    self.doc_target_cb.state(['disabled'])
                    self.cop_target_cb.state(['disabled'])
                except Exception:
                    pass
            return
        else:
            # Fallback: use local GUI-only check
            winner = self.check_win()
            if winner == 'villagers':
                message = 'Villagers win! All Mafia have been eliminated (based on current game state).'
                messagebox.showinfo('Game Over', message)
                self.status.config(text=message)
            elif winner == 'mafia':
                message = 'Mafia win! Mafia control the town (based on current game state).'
                messagebox.showinfo('Game Over', message)
                self.status.config(text=message)
            else:
                message = 'No winner yet (based on current game state).'
                messagebox.showinfo('Win check', message)
                self.status.config(text=message)

    def show_model_popup(self, summary: dict):
        """Display a simple model summary in a popup window."""
        win = tk.Toplevel(self)
        win.title('Model summary')
        win.geometry('600x400')
        txt = tk.Text(win, wrap='none')
        txt.pack(fill='both', expand=True, padx=6, pady=6)
        by_index = summary.get('by_index', {})
        txt.insert('end', 'Domain elements (index -> names):\n')
        for idx in sorted(by_index.keys()):
            names = by_index[idx]
            txt.insert('end', f'  {idx}: {", ".join(names)}\n')

        txt.insert('end', '\nRelations:\n')
        for rname, info in summary.get('relations', {}).items():
            ar = info.get('arity')
            txt.insert('end', f'  {rname} (arity {ar}):\n')
            if ar == 2:
                ds = info.get('domain_size', 0)
                mapping = info.get('mapping', {})
                for i in range(ds):
                    left_names = by_index.get(i, [str(i)])
                    rights = mapping.get(i, [])
                    if rights:
                        right_names = []
                        for j in rights:
                            right_names.extend(by_index.get(j, [str(j)]))
                        txt.insert('end', f'    {"/".join(left_names)} -> {", ".join(right_names)}\n')
                    else:
                        txt.insert('end', f'    {"/".join(left_names)} -> (none)\n')
            else:
                txt.insert('end', f'    values: {info.get("values")}\n')

        btn = ttk.Button(win, text='Close', command=win.destroy)
        btn.pack(pady=6)


if __name__ == '__main__':
    app = GeneratorGUI()
    app.mainloop()
