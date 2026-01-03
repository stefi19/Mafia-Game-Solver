#!/usr/bin/env python3
"""
Check win conditions (villagers or mafia) for a given current game state using Prover9/Mace4.

Usage:
  python3 scripts/check_win_prover9.py --state state.json

State JSON format (example):
{
  "players": ["a","b","c","d"],
  "roles": {"a":"mafia","b":"doctor","c":"cop","d":"villager"},
  "alive": ["a","b","d"],
  "time": "n1"
}

The script writes a temporary .in with the provided facts + win axioms and queries
`villagersWin(<time>)` and `mafiaWin(<time>)`. It uses `scripts.mace4_query` if
available; otherwise it attempts to call `mace4` on PATH.
"""

import argparse
import json
import os
import tempfile
import textwrap
from pathlib import Path
import subprocess
import sys

try:
    import scripts.mace4_query as mq
except Exception:
    mq = None


def build_in_content(state):
    players = state.get('players', [])
    roles = state.get('roles', {})
    alive = set(state.get('alive', []))
    time = state.get('time', 'n1')
    lines = []
    lines.append('% Auto-generated check_win .in')
    lines.append('formulas(assumptions).')

    # role facts
    for p in players:
        r = roles.get(p)
        if r == 'mafia':
            lines.append(f'isMafia({p}).')
        elif r == 'doctor':
            lines.append(f'isDoctor({p}).')
        elif r == 'cop':
            lines.append(f'isCop({p}).')
        elif r == 'villager':
            lines.append(f'isVillager({p}).')

    lines.append('')
    # alive facts at requested time
    for p in alive:
        lines.append(f'alive({p},{time}).')

    lines.append('')
    # Win axioms: villagersWin(N) if no mafia alive at N
    lines.append('% Villagers win: no mafia alive at time N')
    lines.append('all N ( ( all P ( isMafia(P) -> -alive(P,N) ) ) -> villagersWin(N) ).')
    # Mafia win: all alive players are mafia at N (sufficient condition)
    lines.append('% Mafia win: all alive players are mafia at time N (sufficient condition)')
    lines.append('all N ( ( all P ( -alive(P,N) -> isMafia(P) ) ) -> mafiaWin(N) ).')

    lines.append('end.')
    lines.append('')
    lines.append('formulas(goals).')
    lines.append("% queries will be asserted by the runner")
    lines.append('end.')

    return '\n'.join(lines) + '\n'


def run_mace_query_via_subprocess(infile_path: Path, query: str):
    """Fallback: write query file and call mace4 on PATH. Returns (rc, stdout)."""
    # We'll append a temporary goals section with the query.
    with open(infile_path, 'r') as f:
        base = f.read()

    tmpq = infile_path.with_suffix('.q.in')
    with open(tmpq, 'w') as f:
        f.write(base)
        f.write('\n')
        f.write('formulas(goals).\n')
        f.write(query + '.\n')
        f.write('end.\n')

    try:
        p = subprocess.run(['mace4', str(tmpq)], capture_output=True, text=True, timeout=30)
        out = p.stdout + '\n' + p.stderr
        rc = p.returncode
    except FileNotFoundError:
        out = 'mace4 not found on PATH'
        rc = 127
    except Exception as e:
        out = str(e)
        rc = 1
    finally:
        try:
            tmpq.unlink()
        except Exception:
            pass
    return rc, out


def main():
    ap = argparse.ArgumentParser(description='Check win conditions using Prover9/Mace4 for a given game state')
    ap.add_argument('--state', '-s', help='JSON file with state (players, roles, alive, time)')
    ap.add_argument('--inline', '-i', help='Inline JSON string for state (alternative to --state)')
    args = ap.parse_args()

    if not args.state and not args.inline:
        ap.print_help()
        sys.exit(2)

    if args.state:
        p = Path(args.state)
        if not p.exists():
            print(f'State file not found: {p}', file=sys.stderr)
            sys.exit(2)
        state = json.loads(p.read_text())
    else:
        state = json.loads(args.inline)

    content = build_in_content(state)

    # write temp .in
    with tempfile.NamedTemporaryFile('w', suffix='.in', delete=False) as tf:
        tmp_path = Path(tf.name)
        tf.write(content)

    try:
        time = state.get('time', 'n1')
        queries = [f'villagersWin({time})', f'mafiaWin({time})']
        results = {}

        for q in queries:
            if mq is not None:
                try:
                    rc, out, parsed = mq.run_query_return(tmp_path, q)
                except Exception as e:
                    rc, out = 1, str(e)
                    parsed = None
                # if rc == 0 and parsed -> model found containing the predicate
                results[q] = (rc, parsed is not None and bool(parsed))
            else:
                rc, out = run_mace_query_via_subprocess(tmp_path, q)
                # heuristic: if output contains 'Model found' or 'Instance found' treat as true
                lower = out.lower() if out else ''
                sat = ('model found' in lower) or ('instance found' in lower) or ('satisfiable' in lower)
                results[q] = (rc, sat)

        # Interpret results
        vill = results.get(f'villagersWin({time})', (1, False))[1]
        mafi = results.get(f'mafiaWin({time})', (1, False))[1]

        if vill and not mafi:
            print('Villagers win (model found)')
            code = 0
        elif mafi and not vill:
            print('Mafia win (model found)')
            code = 0
        elif mafi and vill:
            print('Both win predicates satisfiable (ambiguous)')
            code = 0
        else:
            print('No winner yet (no model found for win predicates)')
            code = 0

    finally:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except Exception:
            pass

    sys.exit(code)


if __name__ == '__main__':
    main()


def check_state(state: dict):
    """Programmatic API: check the given state dict and return results.

    Returns a dict: {
      'time': str,
      'villagers': bool,
      'mafia': bool,
      'results': {query: (rc, sat_bool)},
    }
    """
    content = build_in_content(state)
    with tempfile.NamedTemporaryFile('w', suffix='.in', delete=False) as tf:
        tmp_path = Path(tf.name)
        tf.write(content)

    try:
        time = state.get('time', 'n1')
        queries = [f'villagersWin({time})', f'mafiaWin({time})']
        results = {}

        for q in queries:
            if mq is not None:
                try:
                    rc, out, parsed = mq.run_query_return(tmp_path, q)
                except Exception as e:
                    rc, out = 1, str(e)
                    parsed = None
                sat = (rc == 0 and parsed is not None and bool(parsed))
                results[q] = (rc, sat)
            else:
                rc, out = run_mace_query_via_subprocess(tmp_path, q)
                lower = out.lower() if out else ''
                sat = ('model found' in lower) or ('instance found' in lower) or ('satisfiable' in lower)
                results[q] = (rc, sat)

        vill = results.get(f'villagersWin({time})', (1, False))[1]
        mafi = results.get(f'mafiaWin({time})', (1, False))[1]
        return {
            'time': time,
            'villagers': vill,
            'mafia': mafi,
            'results': results,
        }
    finally:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except Exception:
            pass
