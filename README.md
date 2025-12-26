AI_Mafia — Toolset for modeling the Mafia game in First-Order Logic (Prover9 / Mace4)

This repository provides a set of practical tools to:
- Generate Prover9 `.in` files that encode Mafia game scenarios.
- Interactively build scenarios with a Tkinter GUI, simulate night/day actions, record votes, and export `.in` files.
- Run finite-model search (Mace4) to check properties such as `alive(a,n1)` and obtain consistent models.
- Provide helper utilities to check "win predicates" (mafia wins / villagers win) against a given game state.

Goal: allow interactive experimentation with FOL encodings of Mafia, provide role-aware suggestions, and test scenario consistency with an automated model finder.

What the project does now (summary)

- GUI (`scripts/gui_generator.py`):
	- Configure number of players and auto-assign roles (mafia, doctor, cop, villager) with a simple heuristic.
	- Generate `.in` files for Prover9/Mace4 and open them in the default editor (on macOS `open` is used).
	- Night controls: choose mafia/doctor/cop targets, apply actions, and run a simple local simulation (a target dies if killed and not protected).
	- Day / Voting UI: add votes, tally, and eliminate a player if there is a unique top vote. UI safeguards:
		- No self-voting.
		- No double voting in the same day.
		- Voters who already voted are hidden from the voter dropdown.
	- "Suggest moves" button: role-aware heuristics and optional short Mace4-based checks (if `mace4_query` is available).
	- "Check alive (Mace4)" button with a concise help (`?`) — runs `alive(player,time)` queries and displays a model summary if one is found.
	- Friendly UI: scrollable content (Canvas + Scrollbar), larger default window size, short elimination flash animation, and strike-through styling for eliminated players.

- Prover9 generator (`scripts/generate_prover9.py`):
	- Produces a `.in` encoding from a `scenario` dict (players, roles, nights, actions, votes).
	- Outputs files into the `prover9/` directory with timestamped names.

- Mace4 wrapper / parser (`scripts/mace4_query.py`):
	- Routines to invoke Mace4 on `.in` files, parse output, and return a structured model summary. The GUI uses `mq.run_query_return` and `mq.summarize_model` when available.

- Programmatic win checker (`scripts/check_win_prover9.py`):
	- `check_state(state: dict)` is provided as a programmatic/CLI entry to evaluate win predicates with the solver.

Important files

- `scripts/gui_generator.py` — main Tkinter GUI. Run with: `python3 scripts/gui_generator.py`.
- `scripts/generate_prover9.py` — `.in` generator used by the GUI.
- `scripts/mace4_query.py` — optional Mace4 runner and parser used to integrate solver checks.
- `scripts/check_win_prover9.py` — programmatic win-check helper.
- `prover9/` — generated `.in` files live here (e.g. `gui_generated_YYYYMMDD_HHMMSS.in`).

Requirements

- Python 3.8+.
- Tkinter (usually included with Python). Verify with:

```bash
python3 -m tkinter
```

- (Optional) Prover9 / Mace4 if you want the GUI's solver-driven features (`Check alive`, `Suggest`) to run locally.

Installation & run steps (macOS / Linux / Windows)

1) Ensure Python is installed (3.8+):

	 - macOS (Homebrew):

```bash
brew install python
```

	 - Ubuntu/Debian:

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip
```

	 - Windows: download and run the installer from https://www.python.org/ and enable "Add to PATH".

2) Ensure Tkinter is available. Test with:

```bash
python3 -m tkinter
```

If a small window appears, Tkinter is present. If not:

- Ubuntu/Debian: `sudo apt install python3-tk`
- macOS/Homebrew: `brew install tcl-tk` (Tkinter is normally bundled with Homebrew Python; additional PATH setup may be required for custom environments)

3) (Optional) Install Prover9 / Mace4 for solver-driven features:

	 - Download from: http://www.cs.unm.edu/~mccune/prover9/
	 - Place `mace4` (and `prover9` if desired) on your PATH so the helper can invoke it (e.g. `which mace4` should locate the binary).

4) Run the GUI from the project root:

```bash
python3 scripts/gui_generator.py
```

Typical GUI workflow

- Set `Number of players` and adjust role counts if desired.
- Click `Generate .in file` → a `.in` file is written to `prover9/` and opened in your editor. The GUI loads the scenario for stepping.
- Night: pick `Mafia target`, `Doctor target`, `Cop investigate`, then `Next night` to apply actions and write an updated `.in`.
- Day / Voting: choose `Voter` and `Vote target`, `Add vote`, then `Tally votes` to eliminate a unique top vote.
- `Check alive (Mace4)`: pick `Player` and `Time` (e.g. `n1`) and run. If Mace4 is available, the GUI will show a model summary when a model exists.
- `Suggest moves`: get role-aware suggestions and optionally run short solver checks to validate certain actions (if Mace4 is present).

Running Mace4 manually

If you prefer to run Mace4 yourself on a generated `.in`:

```bash
# mace4 -f prover9/gui_generated_YYYYMMDD_HHMMSS.in
```

Check the console output for found models or unsat results.

Implementation notes

- Time-indexed predicates (`n0`, `n1`, ...) are used in generated `.in` files to represent states across rounds.
- The GUI uses the `mace4_query` helper to parse solver output and produce a readable model summary; this avoids brittle index calculations in the GUI.

Known limitations & caveats

- The Mace4 output parser can be brittle; some solver outputs may not parse correctly. In those cases the raw output is presented in a popup.
- Degenerate models (domain collapse) are possible. Mitigations include adding distinctness axioms or bounding domain size, but that complicates the encoding.
- Win predicates currently use simple heuristics (villagers win if no mafia alive; mafia win if mafias >= non-mafia). If you want a strict majority encoding in FOL, the generator can be extended to enumerate cases or use encoding tricks.

Suggested next steps

- Improve the Mace4 parser to directly map `alive(player,time)` to a boolean in the GUI.
- Add scenario save/load (JSON) and an undo for eliminations and night steps.
- Improve mousewheel compatibility on Linux (Button-4/5) and refine UI polish.

Contributing

Open an issue or submit a PR. Provide small, focused changes and, where possible, include tests or a short usage example.

Troubleshooting quick checks

- If the GUI fails to import `scripts.generate_prover9`, ensure you are running from the project root and the `scripts/` folder is intact.

```bash
ls scripts/generate_prover9.py
python3 scripts/gui_generator.py
```

- If `mace4` is not found, verify it is installed and on PATH with `which mace4`.

License & author

- Add a `LICENSE` file if you want a formal license (MIT recommended for permissive use).
- Author: Stefi (local repository). Update as needed for contributors.

---