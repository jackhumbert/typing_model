"""End-to-end iPhone layout exploration.

Usage:
    python3 explore.py [--quick] [--original PATH_TO.xkeyboard]

Loads the corpus, scores the current Colemak Ortho board and references,
optimizes letter assignments for one-thumb / two-thumb / hybrid use, emits
.xkeyboard files for the winners into ios/layouts/, and writes results.md.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from layouts_def import (BOTTOM_8, BOTTOM_10, FIXED_8, FIXED_10, LETTERS,
                         LP_8_LETTERS, LP_8_PUNCT, LP_10, SLOTS_8, SLOTS_10,
                         TAP_LETTERS_8, assignment_to_rows, colemak_assignment_10,
                         colemak_ortho, layout_from_assignment, qwerty_ortho,
                         render_ascii)
from optimize import SlotGeometry, anneal, greedy_swaps
from thumbmodel import TrigramScorer, load_corpus, simulate
import xkbgen

HERE = os.path.dirname(os.path.abspath(__file__))
SYMS = LETTERS + " ',.-"


def corpus_stream() -> str:
    return load_corpus([
        (os.path.join(HERE, 'corpus', 'alice.txt'), 1),
        (os.path.join(HERE, 'corpus', 'repo_passage.txt'), 1),
        (os.path.join(HERE, 'corpus', 'mobile_phrases.txt'), 20),
    ])


def perm_from_assignment(assign: dict, letters: list, slots: list) -> list:
    slot_index = {s: i for i, s in enumerate(slots)}
    pos_of = {ch: rc for rc, ch in assign.items()}
    return [slot_index[pos_of[ch]] for ch in letters]


def assignment_from_perm(perm: list, letters: list, slots: list) -> dict:
    return {slots[si]: letters[li] for li, si in enumerate(perm)}


def emit_layouts(source: dict, original: str):
    """Emit .xkeyboard files for the ship list from grid/bottom specs."""
    ship = {
        'colemak_plus': 'Colemak Thumb',
        'opt10_hybrid': 'Opt10 Hybrid',
        'opt8_two': 'Thumbline 8 Two',
        'opt8_one': 'Thumbline 8 One',
        'opt8_hybrid': 'Thumbline 8',
    }
    for tag, disp in ship.items():
        entry = source.get(tag)
        if entry is None:
            continue
        family = entry['family'] if isinstance(entry, dict) else entry.meta.get('family')
        grid = entry['grid'] if isinstance(entry, dict) else entry.grid
        meta = entry.get('meta', {}) if isinstance(entry, dict) else entry.meta
        if tag == 'colemak_plus' and not meta.get('swaps'):
            print('colemak_plus: identical to baseline, skipping emit')
            continue
        rows = [''.join(r) for r in grid]
        if family == '10col':
            bottom = BOTTOM_10
            lp = {',': ['.'], "'": ['@'], '-': ['_']}
        else:
            bottom = BOTTOM_8
            lp = {h: list(v) for h, v in LP_8_PUNCT.items()}
            lp["'"] = lp.get("'", []) + ['@']
            for host, hidden in LP_8_LETTERS.items():
                lp.setdefault(host, []).insert(0, hidden)
        out = os.path.join(HERE, 'layouts', f'{disp.replace(" ", "_")}.xkeyboard')
        xkbgen.generate(original, out, name=disp, rows=rows,
                        bottom=bottom, longpress=lp)
        print('wrote', out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--quick', action='store_true')
    ap.add_argument('--emit-only', action='store_true',
                    help='regenerate .xkeyboard files from layouts.json')
    ap.add_argument('--original', default=os.path.join(HERE, 'layouts',
                                                       'Colemak_Ortho.xkeyboard'))
    args = ap.parse_args()

    if args.emit_only:
        with open(os.path.join(HERE, 'layouts.json')) as f:
            emit_layouts(json.load(f), args.original)
        return

    stream = corpus_stream()
    print(f'corpus: {len(stream)} chars')
    scorer = TrigramScorer(stream, SYMS)
    print(f'trigrams: {len(scorer.tri)}, bigrams: {len(scorer.bi)}')

    g10 = SlotGeometry('10col')
    g8 = SlotGeometry('8col')

    layouts = {}
    layouts['colemak'] = colemak_ortho()
    layouts['qwerty'] = qwerty_ortho()

    iters = 4000 if args.quick else 16000
    restarts = 2 if args.quick else 4
    sub = stream[:60000] if not args.quick else stream[:30000]

    def make_validator(letters, slots, family, w_two, w_one):
        def validate(perm):
            lay = layout_from_assignment(
                'candidate', assignment_from_perm(perm, letters, slots), family)
            r = simulate(lay, sub)
            return w_two * r.ms_per_char_2t + w_one * r.ms_per_char_1t
        return validate

    # --- Colemak micro-iteration: keep the layout, fix the worst offenders
    t0 = time.time()
    cperm = perm_from_assignment(colemak_assignment_10(), list(LETTERS), SLOTS_10)
    perm, e, swaps = greedy_swaps(
        scorer, g10, list(LETTERS), cperm, w_two=0.5, w_one=0.5,
        max_swaps=4, min_gain=0.010,
        validate=make_validator(list(LETTERS), SLOTS_10, '10col', 0.5, 0.5),
        validate_min_gain=0.004)
    print(f'colemak+ swaps: {[(a, b, f"{g*100:.1f}%") for a, b, g in swaps]} '
          f'({time.time()-t0:.0f}s)')
    layouts['colemak_plus'] = layout_from_assignment(
        'Colemak Thumb (micro-iterated)',
        assignment_from_perm(perm, list(LETTERS), SLOTS_10), '10col',
        meta={'swaps': [(a, b) for a, b, _ in swaps]})

    def exact_polish(perm, letters, slots, family, w_two, w_one,
                     rounds=8, min_gain=0.001):
        """All-pairs hill-climb scored by the exact simulator (subsampled).

        The two-thumb landscape is flat (~3% spread) and the trigram
        approximation has a systematic offset there, so final tuning must be
        done against the real model.
        """
        validate = make_validator(letters, slots, family, w_two, w_one)
        e = validate(perm)
        n = len(letters)
        for _ in range(rounds):
            best = (0.0, None)
            for i in range(n):
                for j in range(i + 1, n):
                    perm[i], perm[j] = perm[j], perm[i]
                    gain = (e - validate(perm)) / e
                    perm[i], perm[j] = perm[j], perm[i]
                    if gain > best[0]:
                        best = (gain, (i, j))
            if best[1] is None or best[0] < min_gain:
                break
            i, j = best[1]
            perm[i], perm[j] = perm[j], perm[i]
            e = validate(perm)
        return perm

    # --- full optimizations
    def run(tag, geom, letters, slots, family, w_two, w_one, seed):
        t0 = time.time()
        perm, e = anneal(scorer, geom, letters, w_two=w_two, w_one=w_one,
                         iters=iters, restarts=restarts, seed=seed,
                         verbose=False)
        if args.quick:
            perm, e, _ = greedy_swaps(
                scorer, geom, letters, perm, w_two=w_two, w_one=w_one,
                max_swaps=8, min_gain=0.002,
                validate=make_validator(letters, slots, family, w_two, w_one),
                validate_min_gain=0.0015)
        else:
            perm = exact_polish(perm, letters, slots, family, w_two, w_one)
        print(f'{tag}: {e:.1f} ms/char approx ({time.time()-t0:.0f}s)')
        return assignment_from_perm(perm, letters, slots)

    layouts['opt10_hybrid'] = layout_from_assignment(
        'Opt-10 hybrid (same grid as Colemak)',
        run('opt10_hybrid', g10, list(LETTERS), SLOTS_10, '10col', 0.5, 0.5, 11),
        '10col')
    layouts['opt8_two'] = layout_from_assignment(
        'Thumbline-8 two-thumb',
        run('opt8_two', g8, list(TAP_LETTERS_8), SLOTS_8, '8col', 0.85, 0.15, 22),
        '8col')
    layouts['opt8_one'] = layout_from_assignment(
        'Thumbline-8 one-thumb',
        run('opt8_one', g8, list(TAP_LETTERS_8), SLOTS_8, '8col', 0.15, 0.85, 33),
        '8col')
    layouts['opt8_hybrid'] = layout_from_assignment(
        'Thumbline-8 hybrid',
        run('opt8_hybrid', g8, list(TAP_LETTERS_8), SLOTS_8, '8col', 0.5, 0.5, 44),
        '8col')

    # --- exact scoring
    results = {}
    for tag, lay in layouts.items():
        results[tag] = simulate(lay, stream)
        r = results[tag]
        print(f'{tag:16s} 2T {r.wpm_2t:5.1f} wpm | 1T {r.wpm_1t:5.1f} wpm | '
              f'{r.travel_mm_per_tap:5.2f} mm/tap | alt {r.alternation*100:4.1f}% | '
              f'miss {r.miss_pct:4.2f}% | lp {r.longpress_pct:4.2f}%')

    # --- write results.md + layouts.json
    base = results['colemak']
    lines = [
        '# iPhone 16 thumb-typing layout exploration — results',
        '',
        f'Corpus: {len(stream):,} chars '
        '(Alice in Wonderland + this repo\'s corpus passage + mobile-style '
        'phrases x20). Model: KALQ same-side/alternating thumb equations, '
        'Shannon ID with directional key pitch; miss risk = 2 mm-sigma '
        'Gaussian vs key Voronoi cell. See ios/README.md.',
        '',
        '| layout | key (mm) | 2-thumb WPM | 1-thumb WPM | mm/tap | alt % | miss %/tap | long-press % |',
        '|---|---|---|---|---|---|---|---|',
    ]
    for tag, r in results.items():
        lay = layouts[tag]
        k = lay.keys['e'] if 'e' in lay.keys else list(lay.keys.values())[0]
        rel2 = f' ({(r.wpm_2t/base.wpm_2t-1)*100:+.1f}%)' if tag != 'colemak' else ''
        rel1 = f' ({(r.wpm_1t/base.wpm_1t-1)*100:+.1f}%)' if tag != 'colemak' else ''
        lines.append(
            f'| {lay.name} | {k.w:.1f}x{k.h:.1f} | {r.wpm_2t:.1f}{rel2} | '
            f'{r.wpm_1t:.1f}{rel1} | {r.travel_mm_per_tap:.2f} | '
            f'{r.alternation*100:.1f} | {r.miss_pct:.2f} | {r.longpress_pct:.2f} |')
    lines.append('')
    for tag, lay in layouts.items():
        lines += [f'### {lay.name}', '```', render_ascii(lay), '```', '']
    with open(os.path.join(HERE, 'results.md'), 'w') as f:
        f.write('\n'.join(lines))

    dump = {}
    for tag, lay in layouts.items():
        r = results[tag]
        dump[tag] = {
            'name': lay.name, 'family': lay.meta.get('family'),
            'grid': lay.grid, 'bottom': lay.bottom,
            'meta': {k: v for k, v in lay.meta.items() if k != 'family'},
            'wpm_2t': r.wpm_2t, 'wpm_1t': r.wpm_1t,
            'travel': r.travel_mm_per_tap, 'alternation': r.alternation,
            'miss_pct': r.miss_pct, 'longpress_pct': r.longpress_pct,
            'key_time': r.key_time, 'key_count': r.key_count,
        }
    with open(os.path.join(HERE, 'layouts.json'), 'w') as f:
        json.dump(dump, f, indent=1)

    # --- emit .xkeyboard files
    emit_layouts(layouts, args.original)


if __name__ == '__main__':
    main()
