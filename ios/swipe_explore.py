"""Score the tap+swipe 3x3 family and merge results into layouts.json.

Run after explore.py (it extends that run's layouts.json / results.md).
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from explore import corpus_stream
from layouts_def import SYMBOLS
import swipe_layouts
from swipe_layouts import (build_optimized, direction_error_rate,
                           messagease_classic, thumbkey_en)
from thumbmodel import TrigramScorer, simulate

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    stream = corpus_stream()
    scorer = TrigramScorer(stream, SYMBOLS)

    layouts = {
        'messagease': messagease_classic(),
        'thumbkey': thumbkey_en(),
        'opt9_swipe': build_optimized(stream, scorer),
    }

    results = {}
    for tag, lay in layouts.items():
        r = simulate(lay, stream)
        dir_err = direction_error_rate(lay, r.key_count) * 100
        results[tag] = (r, dir_err)
        print(f'{tag:12s} 2T {r.wpm_2t:5.1f} | 1T {r.wpm_1t:5.1f} | '
              f'swipes {r.longpress_pct:4.1f}% | tap-miss {r.miss_pct:4.2f}% | '
              f'dir-err {dir_err:4.2f}%')

    # sensitivity of the tuned board to the swipe-overhead assumption
    sens = {}
    for delta in (80.0, 110.0, 140.0):
        old = swipe_layouts.SWIPE_MS
        swipe_layouts.SWIPE_MS = delta
        lay = build_optimized(stream, scorer, iters=1, restarts=1)
        # keep the same assignment as the main run for comparability
        swipe_layouts.SWIPE_MS = old
        lay2 = layouts['opt9_swipe']
        # rebuild lay2's keys with the trial overhead
        import copy
        trial = copy.deepcopy(lay2)
        for ch, k in trial.keys.items():
            if k.longpress_ms > 0:
                diag = k.longpress_ms - old > 1e-9
                k.longpress_ms = delta + (swipe_layouts.DIAG_MS if diag else 0.0)
        r = simulate(trial, stream)
        sens[int(delta)] = {'wpm_2t': r.wpm_2t, 'wpm_1t': r.wpm_1t}
        print(f'  sensitivity swipe_ms={delta:.0f}: 2T {r.wpm_2t:.1f} / 1T {r.wpm_1t:.1f}')

    path = os.path.join(HERE, 'layouts.json')
    with open(path) as f:
        dump = json.load(f)
    for tag, lay in layouts.items():
        r, dir_err = results[tag]
        dump[tag] = {
            'name': lay.name, 'family': '3x3',
            'grid': lay.grid, 'bottom': lay.bottom,
            'meta': {'swipemap': lay.meta['swipemap'],
                     'source': lay.meta.get('source')},
            'wpm_2t': r.wpm_2t, 'wpm_1t': r.wpm_1t,
            'travel': r.travel_mm_per_tap, 'alternation': r.alternation,
            'miss_pct': r.miss_pct, 'dir_err_pct': dir_err,
            'longpress_pct': r.longpress_pct,
            'key_time': r.key_time, 'key_count': r.key_count,
        }
    dump.setdefault('_meta', {})['swipe_sensitivity'] = sens
    with open(path, 'w') as f:
        json.dump(dump, f, indent=1)
    print('merged into layouts.json')

    lines = ['', '## Swipe family (3x3 tap+swipe, MessagEase style)', '',
             '| layout | 2-thumb WPM | 1-thumb WPM | swipe % | tap-miss % | dir-err % |',
             '|---|---|---|---|---|---|']
    for tag, lay in layouts.items():
        r, dir_err = results[tag]
        lines.append(f'| {lay.name} | {r.wpm_2t:.1f} | {r.wpm_1t:.1f} | '
                     f'{r.longpress_pct:.1f} | {r.miss_pct:.2f} | {dir_err:.2f} |')
    lines.append('')
    lines.append(f'Swipe-overhead sensitivity (corpus-tuned board): '
                 + ', '.join(f'{k} ms → {v["wpm_1t"]:.1f} 1T wpm'
                             for k, v in sens.items()))
    md = os.path.join(HERE, 'results.md')
    with open(md) as f:
        content = f.read()
    marker = '## Swipe family'
    if marker in content:
        content = content[:content.index(marker)].rstrip() + '\n'
    with open(md, 'w') as f:
        f.write(content + '\n'.join(lines) + '\n')
    print('updated results.md')


if __name__ == '__main__':
    main()
