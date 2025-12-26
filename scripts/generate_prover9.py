#!/usr/bin/env python3
"""
generate_prover9.py

Simple generator that emits a Prover9/Mace4 `.in` file modeling a multi-night Mafia scenario.

Usage (quick):
  python3 scripts/generate_prover9.py   # writes prover9/multi_night_example.in using the built-in scenario

The generator performs simple voting tallying and will mark a player as eliminated if they receive strictly the most votes (unique max) on a day.
Elimination is then asserted as `-Alive(player, next_night)` in the produced `.in` file.
"""

import json
import os
from collections import Counter, defaultdict

OUT_PATH = os.path.join(os.path.dirname(__file__), '..', 'prover9', 'multi_night_example.in')

# Small example scenario — modify as desired
# Players are single-letter constants (a,b,c,d,e,...)
scenario = {
    "players": ["a", "b", "c", "d", "e"],
    "roles": {
        "a": "mafia",
        "b": "doctor",
        "c": "cop",
        "d": "villager",
        "e": "villager"
    },
    # number of nights to simulate
    "nights": 2,
    # actions per night: lists of dicts with action type
    # kill: {"by":"a","target":"d"}
    # protect: {"by":"b","target":"d"}
    # investigate: {"by":"c","target":"a"}
    "night_actions": {
        "0": [
            {"type": "kill", "by": "a", "target": "d"},
            {"type": "protect", "by": "b", "target": "d"},
            {"type": "investigate", "by": "c", "target": "a"}
        ],
        "1": [
            {"type": "kill", "by": "a", "target": "e"},
            {"type": "protect", "by": "b", "target": "a"},
            {"type": "investigate", "by": "c", "target": "a"}
        ]
    },
    # votes per day (day 0 is after night 0). Accepts lists of voter->target pairs.
    # votes are used to compute an elimination if there is a unique top vote-getter.
    "day_votes": {
        "0": [
            {"voter": "a", "target": "e"},
            {"voter": "b", "target": "e"},
            {"voter": "c", "target": "e"},
            {"voter": "d", "target": "e"},
            {"voter": "e", "target": "a"}
        ],
        "1": [
            {"voter": "a", "target": "b"},
            {"voter": "b", "target": "a"},
            {"voter": "c", "target": "a"},
            {"voter": "d", "target": "a"}
        ]
    }
}


def time_const(i):
    return f"n{i}"


def write_in(path, scenario):
    players = scenario["players"]
    roles = scenario.get("roles", {})
    nights = int(scenario.get("nights", 1))
    night_actions = scenario.get("night_actions", {})
    day_votes = scenario.get("day_votes", {})

    # compute which players are eliminated by votes (generator handles tallying)
    eliminated_by_day = {}
    for day_str, votes in day_votes.items():
        day = int(day_str)
        cnt = Counter([v["target"] for v in votes])
        if not cnt:
            continue
        most_common = cnt.most_common()
        top_count = most_common[0][1]
        top = [p for p, c in most_common if c == top_count]
        if len(top) == 1:
            eliminated_by_day[day] = top[0]

    with open(path, 'w') as f:
        f.write("% Auto-generated Prover9 input: multi-night Mafia example\n")
        f.write("% Nights: {}\n\n".format(nights))

        # assumptions
        f.write("formulas(assumptions).\n")

        # role facts
        for p in players:
            r = roles.get(p)
            if r == 'mafia':
                f.write(f"isMafia({p}).\n")
            elif r == 'doctor':
                f.write(f"isDoctor({p}).\n")
            elif r == 'cop':
                f.write(f"isCop({p}).\n")
            elif r == 'villager':
                f.write(f"isVillager({p}).\n")
            else:
                # unspecified role — leave it out
                pass

        f.write('\n')

        # time constants and Next relation
        for i in range(nights + 1):
            f.write(f"% time constant\n")
            f.write(f"% {time_const(i)}\n")
        f.write('\n')
        for i in range(nights):
            f.write(f"next({time_const(i)},{time_const(i+1)}).\n")
        f.write('\n')

        # Alive at initial night n0
        for p in players:
            f.write(f"alive({p},{time_const(0)}).\n")
        f.write('\n')

        # Night actions
        for i in range(nights):
            acts = night_actions.get(str(i), [])
            for act in acts:
                typ = act.get('type')
                by = act.get('by')
                target = act.get('target')
                if typ == 'kill':
                    f.write(f"kill({by},{target},{time_const(i)}).\n")
                elif typ == 'protect':
                    f.write(f"protect({by},{target},{time_const(i)}).\n")
                elif typ == 'investigate':
                    f.write(f"investigate({by},{target},{time_const(i)}).\n")
            f.write('\n')

        # Day eliminations (generator computed)
        for day, player in eliminated_by_day.items():
            # day corresponds to after night `day` -> which is time_const(day+1)
            t = time_const(day+1)
            f.write(f"% elimination by vote on day {day}\n")
            f.write(f"eliminated({player},{t}).\n")
            # assert explicitly not alive at that time — we do this on generator side
            f.write(f"-alive({player},{t}).\n")
            f.write('\n')

        # Axioms (time-indexed)
        f.write("% Axioms\n")
        # Protect leads to Protected at same night
        f.write("all D all Y all N ( protect(D,Y,N) -> protected(Y,N) ).\n")
        # Kill without Protected causes death at next time (quantify M = next time)
        f.write("all X all Y all N all M ( kill(X,Y,N) & -protected(Y,N) & next(N,M) -> -alive(Y,M) ).\n")
        # Investigate outcome
        f.write("all C all T all N ( isCop(C) & isMafia(T) & investigate(C,T,N) -> recognizes(C,T) ).\n")
        f.write('\n')
        # Win condition predicates (simple, time-indexed)
        # Villagers win at time N if no mafia is alive at N
        f.write('% Villagers win: no mafia alive at time N\n')
        f.write('all N ( ( all P ( isMafia(P) -> -alive(P,N) ) ) -> villagersWin(N) ).\n')
        # Mafia win at time N if all alive players are mafia (i.e., no non-mafia alive)
        f.write('% Mafia win: all alive players are mafia at time N (sufficient condition)\n')
        f.write('all N ( ( all P ( -alive(P,N) -> isMafia(P) ) ) -> mafiaWin(N) ).\n')
        # (persistence axiom removed — previously used nested negation that caused
        # Mace4 to complain about symbol usage conflicts; keeping axioms minimal)

        f.write("end.\n\n")

        # Goals: for convenience we assert no specific goal; user can add queries to prove
        f.write("formulas(goals).\n")
        f.write("% Add goals here, e.g. -Alive(e,n1) or Recognizes(c,a).\n")
        f.write("end.\n")

    print(f"Wrote {path}")


if __name__ == '__main__':
    out = os.path.abspath(OUT_PATH)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    write_in(out, scenario)
