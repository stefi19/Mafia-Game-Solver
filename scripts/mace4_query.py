#!/usr/bin/env python3
"""
mace4_query.py

Insert a query (e.g. Alive(a,n1) or -Alive(a,n1)) into a Prover9/Mace4 `.in` file's assumptions
and run Mace4 to search for a finite model satisfying the augmented assumptions.

Usage:
  python3 scripts/mace4_query.py --file prover9/multi_night_example.in --query "-Alive(e,n1)"

If Mace4 is not installed or on PATH the script will print an informative error.
"""

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def insert_query_into_assumptions(text: str, query: str) -> str:
    marker = 'formulas(assumptions).'
    idx = text.find(marker)
    if idx == -1:
        raise ValueError('Could not find "formulas(assumptions)." in the input file')
    # find the end of the assumptions block (first occurrence of a line that is exactly 'end.' after idx)
    rest = text[idx:]
    end_marker = '\nend.\n'
    end_idx = rest.find(end_marker)
    if end_idx == -1:
        # try without surrounding newlines
        end_marker = 'end.'
        end_idx = rest.find(end_marker)
        if end_idx == -1:
            raise ValueError('Could not find end of assumptions ("end.")')
    insert_pos = idx + end_idx
    # build new text: before insert_pos + query + then rest from insert_pos
    before = text[:insert_pos]
    after = text[insert_pos:]
    qline = query.strip()
    if not qline.endswith('.'):
        qline = qline + '.'
    new_text = before + qline + '\n' + after
    return new_text


def run_mace4(onfile: Path, mace4_cmd: str = 'mace4') -> int:
    cmd = [mace4_cmd, '-f', str(onfile)]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    return proc.returncode, proc.stdout


def parse_mace_model_output(output: str) -> dict:
    """Parse a Mace4 model output and return a dict with functions and relations.

    Returns a structure: { 'functions': {name: [ints...]}, 'relations': {name: {'arity':k, 'values':[0/1...]}} }
    If no model found or parsing fails, returns empty dict.
    """
    import re

    data = {'functions': {}, 'relations': {}}
    # find the interpretation block
    m = re.search(r"interpretation\s*\(.*?\,\s*\[.*?\],\s*\[\s*(.*?)\]\)\.", output, re.S)
    # The above attempt can be brittle; instead parse lines for 'function(' and 'relation('
    func_re = re.compile(r"function\(([^,]+)\s*,\s*\[([^\]]*)\]\)")
    rel_re = re.compile(r"relation\(([^,\(]+\([^\)]*\))\s*,\s*\[([^\]]*)\]\)" )

    for fm in func_re.finditer(output):
        name = fm.group(1).strip()
        vals = [int(x) for x in fm.group(2).split(',') if x.strip()]
        data['functions'][name] = vals

    for rm in rel_re.finditer(output):
        name = rm.group(1).strip()  # e.g. alive(_,_)
        vals = [int(x) for x in rm.group(2).split(',') if x.strip()]
        # determine arity by counting underscores or commas inside parentheses
        arity = name.count('_')
        data['relations'][name] = {'arity': arity, 'values': vals}

    return data


def summarize_model(parsed: dict) -> dict:
    """Create a human-friendly summary from parsed model data.

    Returns {'functions':..., 'relations':...} essentially passed through but grouped.
    """
    # Build inverse map from functions: index -> [names]
    inv = {}
    for name, vals in parsed.get('functions', {}).items():
        if not vals:
            continue
        idx = vals[0]
        inv.setdefault(idx, []).append(name)

    summary = {'by_index': inv, 'relations': {}}
    # For binary relations like alive, attempt to produce a readable mapping
    for rname, info in parsed.get('relations', {}).items():
        arity = info.get('arity', 0)
        vals = info.get('values', [])
        if arity == 2:
            # try determine domain size
            import math
            ds = int(round(math.sqrt(len(vals)))) if vals else 0
            mapping = {}
            for i in range(ds):
                for j in range(ds):
                    idx = i * ds + j
                    v = vals[idx] if idx < len(vals) else 0
                    if v:
                        mapping.setdefault(i, []).append(j)
            summary['relations'][rname] = {'arity': 2, 'mapping': mapping, 'domain_size': ds}
        else:
            summary['relations'][rname] = {'arity': arity, 'values': vals}

    return summary


def _collect_constants_from_text(text: str) -> list:
    import re
    args = set()
    # find predicate argument lists and extract tokens that look like constants
    for m in re.finditer(r"\b[a-z][a-z0-9_]*\s*\(([^)]*)\)", text):
        inside = m.group(1)
        for part in inside.split(','):
            tok = part.strip()
            # accept lower-case tokens (constants) like a, n0, player1
            if tok and re.match(r"^[a-z][a-z0-9_]*$", tok):
                args.add(tok)
    return sorted(args)


def run_query_return(parsed_file: Path, query: str, mace4_cmd: str = 'mace4', max_domain: int = None):
    """Insert query into file, optionally add domain constraints, run Mace4, return (rc, stdout, parsed_model).

    If max_domain is set (int), this function will add domain constants dom0..dom{max_domain-1}
    and assert that every constant found in the file equals one of those dom constants, which
    restricts Mace4 to models with at most that many distinct elements.
    """
    # read file
    text = parsed_file.read_text()
    # collect constants from the original file
    consts = _collect_constants_from_text(text)

    # build domain constraint block if requested
    domain_block = ''
    if max_domain and max_domain > 0:
        dom_names = [f'dom{i}' for i in range(max_domain)]
        # declare domain constants
        domain_block += '\n% domain constants forced by wrapper\n'
        for d in dom_names:
            domain_block += f'{d}.\n'
        # for each constant in file, assert it equals one of the domain constants
        for c in consts:
            disj = ' | '.join([f'{c} = {d}' for d in dom_names])
            domain_block += f'({disj}).\n'

    new_text = insert_query_into_assumptions(text, query)
    if domain_block:
        # insert domain_block just before the end. Find the first occurrence of '\nend.\n' after assumptions
        idx = new_text.find('\nend.\n')
        if idx != -1:
            new_text = new_text[:idx] + domain_block + new_text[idx:]

    with tempfile.NamedTemporaryFile('w', suffix='.in', delete=False) as tf:
        tf.write(new_text)
        tmpname = tf.name

    rc, out = run_mace4(Path(tmpname), mace4_cmd=mace4_cmd)
    parsed = {}
    if rc == 0:
        parsed = parse_mace_model_output(out)
    return rc, out, parsed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--file', '-f', required=True, help='Path to a Prover9/Mace4 .in file')
    parser.add_argument('--query', '-q', required=True, help='Query to assert in assumptions, e.g. "Alive(a,n1)" or "-Alive(a,n1)"')
    parser.add_argument('--mace4', default='mace4', help='Mace4 executable name or path')
    args = parser.parse_args()

    mace4_path = shutil.which(args.mace4)
    if mace4_path is None:
        print(f'Error: could not find Mace4 on PATH as "{args.mace4}". Install Prover9/Mace4 (e.g. `brew install prover9`) or set --mace4 path.')
        sys.exit(2)

    p = Path(args.file)
    if not p.exists():
        print(f'Error: file not found: {p}')
        sys.exit(2)

    text = p.read_text()
    try:
        new_text = insert_query_into_assumptions(text, args.query)
    except ValueError as e:
        print('Error while preparing file:', e)
        sys.exit(2)

    with tempfile.NamedTemporaryFile('w', suffix='.in', delete=False) as tf:
        tf.write(new_text)
        tmpname = tf.name

    print(f'Running Mace4 on temporary file: {tmpname}\n(looking for a model that satisfies the augmented assumptions)')
    rc = run_mace4(Path(tmpname), mace4_cmd=mace4_path)
    if rc == 0:
        print('\nMace4 exited with code 0. Check above for model output (if any).')
    else:
        print(f'\nMace4 exited with code {rc}. See output above for details.')


if __name__ == '__main__':
    main()
