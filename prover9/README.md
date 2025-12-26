# Quick guide: Modeling Mafia in First-Order Logic for Prover9 / Mace4

This folder contains small example encodings that model night actions in a simple
Mafia (Werewolf) setting. These examples model outcomes (what ends up true), not
epistemic knowledge (what players know).

Included files:
- `mafia_kill_without_protect.in` — scenario: Mafia kills a villager (d); Doctor does NOT protect; goal: show d is dead.
- `mafia_kill_with_protect.in` — scenario: Mafia kills d but Doctor protects d; goal: `-alive(d)` should NOT be provable.
- `mafia_investigate.in` — scenario: Cop investigates a player who is Mafia; goal: show `recognizes(c,a)`.

Common FOL concepts used (predicates & facts):
- isMafia(X), isDoctor(X), isCop(X), isVillager(X)
- alive(X)
- kill(Killer, Victim)
- protect(Doctor, Target)  -> yields protected(Target)
- protected(X)  (derived from protect)
- investigate(Cop, Target) -> recognizes(Cop, Target) (outcome of investigation)

Key axioms (found in the .in files):
- all X all Y ( kill(X,Y) & ~protected(Y) -> -alive(Y) ).
- all D all Y ( protect(D,Y) -> protected(Y) ).
- all C all T ( isCop(C) & isMafia(T) & investigate(C,T) -> recognizes(C,T) ).

How to run Prover9 and Mace4 (macOS):
1) Install (if you don't have it):
   brew install prover9

2) Run Prover9 (proof search):
   prover9 -f mafia_kill_without_protect.in

   Prover9 will try to prove the formulas in the `formulas(goals)` section.

3) Run Mace4 (finite model search — useful when Prover9 doesn't find a proof and
   you want a concrete model):
   mace4 -f mace4_kill_with_protect.in

   Mace4 will try to find a finite model satisfying the `formulas(assumptions)`.

Included Mace4 examples:
- `prover9/mace4_kill_with_protect.in` — simple scenario: mafia kills, doctor protects; used for model finding.
- `prover9/mace4_multi_night.in` — a generated multi-night encoding, useful to check time-indexed axioms across steps.

Generator and GUI
- Use `scripts/generate_prover9.py` to programmatically build scenarios and write `.in` files.
- A small Tkinter GUI is available at `scripts/gui_generator.py` to create scenarios, step nights,
  and run model checks via Mace4 (if installed).

Limitations & possible extensions
- This encoding does not capture epistemic knowledge (who knows what). It uses standard FOL only.
- To model multi-night play, time indices (n0, n1, ...) or time functions are used; extend axioms accordingly.
- To model stricter rules (e.g. doctor can protect only one player per night, mafia size > 1, voting rules), add appropriate axioms and constraints.

Suggested next improvements I can help with:
- Add explicit time-indexed variants and day/night rules.
- Add voting and day elimination rules.
- Add a `mafiaWins` / `townWins` predicate and a simple scorer to evaluate best actions over several steps (requires expanding axioms and testing).

