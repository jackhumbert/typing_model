"""Tap + directional-swipe 3x3 layouts (the MessagEase / Thumb-Key family).

One more geometry family, following the user's pointer at the 3x3
tap-plus-swipe grids from Android: 9 huge keys (~20.7 x 7.1 mm here — a third
of the screen width each), the ~9 most frequent letters on plain taps, the
rest entered by swiping a direction on a key. Rationale for precision: tap
targets this large make Gaussian tap misses essentially impossible, and a
direction is far harder to fumble than a 6 mm key.

Movement model: identical Fitts machinery as the tap families (travel between
key centres barely matters — IDs sit at the clamp floor), plus a per-action
swipe overhead. Yamanaka, Usuba & Sato (CHI 2024, "Behavioral Differences
between Tap and Swipe") measured swipes as reliably slower and more
error-prone than taps on the same targets; the magnitude here is a
parameter:

    SWIPE_MS  = 110  extra ms per swipe vs a tap (sensitivity-checked 80-140)
    DIAG_MS   = 30   additional cost for diagonal (8-way) swipes
    ERR_CARDINAL = 1.0%  assumed direction-error rate, 4-way swipes
    ERR_DIAGONAL = 3.0%  assumed direction-error rate, diagonals

Reference layouts are transcribed from the Thumb-Key project's
ENMessagEase.kt / ENThumbKey.kt (which mirror classic MessagEase); their
space/return conventions are replaced by this board's own bottom function row,
and missing symbols from our corpus set are placed on spare directions
(documented inline).
"""

from __future__ import annotations

import math
import random

import numpy as np

from layouts_def import BOTTOM_10, LETTERS
from thumbmodel import (CELL_GAP, INSET_LEFT, INSET_RIGHT, INSET_TOP, Key,
                        Layout, MM_PER_PT, ROW_GAP, SCREEN_W_PT,
                        row_height_pt)

SWIPE_MS = 110.0
DIAG_MS = 30.0
ERR_CARDINAL = 0.010
ERR_DIAGONAL = 0.030

CARDINALS = {'n', 's', 'e', 'w'}
DIAGONALS = {'ne', 'nw', 'se', 'sw'}

# cell index: 0 1 2 / 3 4 5 / 6 7 8   (4 = hub)
TOWARD_HUB = {0: 'se', 1: 's', 2: 'sw', 3: 'e', 5: 'w', 6: 'ne', 7: 'n', 8: 'nw'}


def grid3_layout(name: str, cells: list[dict], *, meta: dict | None = None) -> Layout:
    """cells: 9 dicts {'tap': ch, 'swipes': {dir: ch}} in row-major order."""
    n_cols = 3
    kw = (SCREEN_W_PT - INSET_LEFT - INSET_RIGHT - (n_cols - 1) * CELL_GAP) / n_cols
    rh = row_height_pt()
    lay = Layout(name=name, n_cols=n_cols, meta={'family': '3x3', **(meta or {})})
    lay.grid = [[cells[r * 3 + c]['tap'] for c in range(3)] for r in range(3)]
    lay.bottom = [c for c, _ in BOTTOM_10]
    swipemap: dict[str, dict[str, str]] = {}

    def add(ch, x_pt, y_pt, w_pt, h_pt, extra=0.0):
        lay.keys[ch] = Key(
            char=ch, x=x_pt * MM_PER_PT, y=y_pt * MM_PER_PT,
            w=w_pt * MM_PER_PT, h=h_pt * MM_PER_PT,
            pitch_w=(w_pt + CELL_GAP) * MM_PER_PT,
            pitch_h=(h_pt + ROW_GAP) * MM_PER_PT,
            longpress_ms=extra,
        )

    for i, spec in enumerate(cells):
        r, c = divmod(i, 3)
        x = INSET_LEFT + c * (kw + CELL_GAP) + kw / 2
        y = INSET_TOP + r * (rh + ROW_GAP) + rh / 2
        add(spec['tap'], x, y, kw, rh)
        swipemap[spec['tap']] = dict(spec.get('swipes', {}))
        for d, ch in spec.get('swipes', {}).items():
            extra = SWIPE_MS + (DIAG_MS if d in DIAGONALS else 0.0)
            add(ch, x, y, kw, rh, extra=extra)

    # bottom function row: identical to the user's current board
    usable = SCREEN_W_PT - INSET_LEFT - INSET_RIGHT - 4 * CELL_GAP
    w = usable / 5
    y = INSET_TOP + 3 * (rh + ROW_GAP) + rh / 2
    add(' ', INSET_LEFT + 3 * (w + CELL_GAP) + w / 2, y, w, rh)
    lay.meta['swipemap'] = swipemap
    return lay


def direction_error_rate(lay: Layout, key_count: dict[str, float]) -> float:
    """Expected direction-fumble probability per character."""
    total = sum(key_count.values())
    if not total:
        return 0.0
    err = 0.0
    for tap, swipes in lay.meta['swipemap'].items():
        for d, ch in swipes.items():
            rate = ERR_DIAGONAL if d in DIAGONALS else ERR_CARDINAL
            err += key_count.get(ch, 0.0) * rate
    return err / total


# ------------------------------------------------------------------ references

def messagease_classic() -> Layout:
    """Classic MessagEase English (via thumb-key's ENMessagEase.kt).

    Deviations for this board: '-' takes the free west direction of the
    'i' key (classic has it in symbol mode); ':' dropped (not in corpus set).
    """
    return grid3_layout('MessagEase classic', [
        {'tap': 'a', 'swipes': {'se': 'v'}},
        {'tap': 'n', 'swipes': {'s': 'l'}},
        {'tap': 'i', 'swipes': {'sw': 'x', 'w': '-'}},
        {'tap': 'h', 'swipes': {'e': 'k'}},
        {'tap': 'o', 'swipes': {'nw': 'q', 'n': 'u', 'ne': 'p',
                                'w': 'c', 'e': 'b',
                                'sw': 'g', 's': 'd', 'se': 'j'}},
        {'tap': 'r', 'swipes': {'w': 'm'}},
        {'tap': 't', 'swipes': {'ne': 'y'}},
        {'tap': 'e', 'swipes': {'n': 'w', 'ne': "'", 'e': 'z',
                                'sw': ',', 's': '.'}},
        {'tap': 's', 'swipes': {'nw': 'f'}},
    ], meta={'source': 'transcribed'})


def thumbkey_en() -> Layout:
    """Thumb-Key EN v4 (ENThumbKey.kt). ',' replaces its '*' on i-southwest."""
    return grid3_layout('Thumb-Key EN', [
        {'tap': 's', 'swipes': {'se': 'w'}},
        {'tap': 'r', 'swipes': {'s': 'g'}},
        {'tap': 'o', 'swipes': {'sw': 'u'}},
        {'tap': 'n', 'swipes': {'e': 'm'}},
        {'tap': 'h', 'swipes': {'nw': 'j', 'n': 'q', 'ne': 'b',
                                'w': 'k', 'e': 'p',
                                'sw': 'v', 's': 'x', 'se': 'y'}},
        {'tap': 'a', 'swipes': {'w': 'l'}},
        {'tap': 't', 'swipes': {'ne': 'c'}},
        {'tap': 'i', 'swipes': {'n': 'f', 'ne': "'", 'e': 'z',
                                'sw': ',', 's': '.', 'se': '-'}},
        {'tap': 'e', 'swipes': {'nw': 'd'}},
    ], meta={'source': 'transcribed'})


# ------------------------------------------------------------------ optimizer

def build_optimized(stream: str, scorer, *, seed=7, iters=9000, restarts=3,
                    w_two=0.5, w_one=0.5) -> Layout:
    """Corpus-tuned 3x3, following Thumb-Key's construction principle:

    ranks 1-9 by frequency -> taps; ranks 10-17 -> centerward swipes on the
    eight edge keys; ranks 18-25 -> the hub's eight directions (most frequent
    of those on cardinals); z -> spare edge direction; , . ' - fixed on the
    bottom-right key (the corner the user's punctuation already lives in).
    Simulated annealing permutes tap positions and centerward hosts.
    """
    from collections import Counter
    freq = Counter(c for c in stream if c in LETTERS)
    ranked = [c for c, _ in freq.most_common()]
    taps = ranked[:9]
    centerward = ranked[9:17]
    hub_letters = ranked[17:25]
    last = ranked[25]

    kw_mm = ((SCREEN_W_PT - INSET_LEFT - INSET_RIGHT - 2 * CELL_GAP) / 3) * MM_PER_PT
    rh_mm = row_height_pt() * MM_PER_PT
    centres = []
    for i in range(9):
        r, c = divmod(i, 3)
        x = (INSET_LEFT + c * ((SCREEN_W_PT - 6 - 12) / 3 + CELL_GAP)
             + (SCREEN_W_PT - 6 - 12) / 6) * MM_PER_PT
        y = (INSET_TOP + r * (row_height_pt() + ROW_GAP) + row_height_pt() / 2) * MM_PER_PT
        centres.append((x, y))

    from optimize import SYM_INDEX
    from layouts_def import SYMBOLS
    split = SCREEN_W_PT * MM_PER_PT / 2
    n = len(SYMBOLS)

    # space geometry: bottom row key 4 of 5
    usable = SCREEN_W_PT - INSET_LEFT - INSET_RIGHT - 4 * CELL_GAP
    sw_pt = usable / 5
    sp_x = (INSET_LEFT + 3 * (sw_pt + CELL_GAP) + sw_pt / 2) * MM_PER_PT
    sp_y = (INSET_TOP + 3 * (row_height_pt() + ROW_GAP) + row_height_pt() / 2) * MM_PER_PT

    def arrays(tap_perm, cw_perm):
        """tap_perm: cell index for each of taps[]; cw_perm: edge-cell index
        (0-7 over the 8 non-hub cells) for each of centerward[]."""
        xs = np.zeros(n); ys = np.zeros(n)
        pw = np.full(n, kw_mm + CELL_GAP * MM_PER_PT)
        ph = np.full(n, rh_mm + ROW_GAP * MM_PER_PT)
        lp = np.zeros(n)
        edge_cells = [i for i in range(9) if i != 4]
        for li, cell in zip(taps, tap_perm):
            i = SYM_INDEX[li]
            xs[i], ys[i] = centres[cell]
        for li, e in zip(centerward, cw_perm):
            i = SYM_INDEX[li]
            xs[i], ys[i] = centres[edge_cells[e]]
            lp[i] = SWIPE_MS
        for k, li in enumerate(hub_letters):
            i = SYM_INDEX[li]
            xs[i], ys[i] = centres[4]
            lp[i] = SWIPE_MS + (0.0 if k < 4 else DIAG_MS)
        i = SYM_INDEX[last]
        xs[i], ys[i] = centres[6]      # spare direction on bottom-left key
        lp[i] = SWIPE_MS + DIAG_MS
        for ch, extra in [(',', SWIPE_MS), ('.', SWIPE_MS),
                          ("'", SWIPE_MS + DIAG_MS), ('-', SWIPE_MS + DIAG_MS)]:
            i = SYM_INDEX[ch]
            xs[i], ys[i] = centres[8]  # bottom-right corner key
            lp[i] = extra
        i = SYM_INDEX[' ']
        xs[i], ys[i] = sp_x, sp_y
        pw[i] = (sw_pt + CELL_GAP) * MM_PER_PT
        side = (xs >= split).astype(np.int64)
        return xs, ys, pw, ph, side, lp

    def energy(tp, cp):
        xs, ys, pw, ph, side, lp = arrays(tp, cp)
        return scorer.score(xs, ys, pw, ph, side, lp, w_two, w_one)[0]

    rng = random.Random(seed)
    best = (math.inf, None, None)
    for r in range(restarts):
        tp = rng.sample(range(9), 9)
        cp = rng.sample(range(8), 8)
        e = energy(tp, cp)
        t0, t1 = e * 0.02, e * 0.0005
        for it in range(iters):
            t = t0 * (t1 / t0) ** (it / iters)
            if rng.random() < 0.5:
                i, j = rng.randrange(9), rng.randrange(9)
                tp[i], tp[j] = tp[j], tp[i]
                e2 = energy(tp, cp)
                if e2 < e or rng.random() < math.exp((e - e2) / t):
                    e = e2
                else:
                    tp[i], tp[j] = tp[j], tp[i]
            else:
                i, j = rng.randrange(8), rng.randrange(8)
                cp[i], cp[j] = cp[j], cp[i]
                e2 = energy(tp, cp)
                if e2 < e or rng.random() < math.exp((e - e2) / t):
                    e = e2
                else:
                    cp[i], cp[j] = cp[j], cp[i]
        if e < best[0]:
            best = (e, list(tp), list(cp))

    _, tp, cp = best
    edge_cells = [i for i in range(9) if i != 4]
    cells = [{'tap': None, 'swipes': {}} for _ in range(9)]
    for li, cell in zip(taps, tp):
        cells[cell]['tap'] = li
    for li, e in zip(centerward, cp):
        cell = edge_cells[e]
        cells[cell]['swipes'][TOWARD_HUB[cell]] = li
    hub_dirs = ['n', 'e', 'w', 's', 'ne', 'nw', 'se', 'sw']
    for d, li in zip(hub_dirs, hub_letters):
        cells[4]['swipes'][d] = li
    # z and punctuation on spare directions
    spare6 = next(d for d in ['sw', 's', 'w', 'se']
                  if d not in cells[6]['swipes'] and d != TOWARD_HUB[6])
    cells[6]['swipes'][spare6] = last
    for d, ch in [('e', ','), ('s', '.'), ('se', "'"), ('sw', '-')]:
        if d not in cells[8]['swipes']:
            cells[8]['swipes'][d] = ch
    return grid3_layout('Swipe-9 (corpus-tuned)', cells,
                        meta={'source': 'optimized'})
