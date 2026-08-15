"""Simulated-annealing letter-assignment optimizer.

Mirrors the hybrid search used for KALQ (random starts -> local search ->
annealing) in a simpler multi-restart annealer.  The objective is the
trigram-approximated blend of two-thumb and one-thumb ms/char from
thumbmodel.TrigramScorer; final numbers always come from the exact stream
simulation in thumbmodel.simulate.
"""

from __future__ import annotations

import math
import random

import numpy as np

from layouts_def import (FIXED_8, FIXED_10, LP_8_LETTERS, SLOTS_8, SLOTS_10,
                         SYMBOLS, TAP_LETTERS_8)
from thumbmodel import (CELL_GAP, INSET_LEFT, INSET_RIGHT, INSET_TOP,
                        LONGPRESS_MS, MM_PER_PT, ROW_GAP, SCREEN_W_PT,
                        key_width_pt, row_height_pt)

SYM_INDEX = {c: i for i, c in enumerate(SYMBOLS)}


class SlotGeometry:
    """Precomputed slot centres + fixed symbol positions for one family."""

    def __init__(self, family: str):
        self.family = family
        n_cols = 10 if family == '10col' else 8
        self.slots = SLOTS_10 if family == '10col' else SLOTS_8
        fixed = FIXED_10 if family == '10col' else FIXED_8
        kw = key_width_pt(n_cols)
        rh = row_height_pt()
        self.pitch_w = (kw + CELL_GAP) * MM_PER_PT
        self.pitch_h = (rh + ROW_GAP) * MM_PER_PT

        def centre(r, c):
            x = INSET_LEFT + c * (kw + CELL_GAP) + kw / 2
            y = INSET_TOP + r * (rh + ROW_GAP) + rh / 2
            return x * MM_PER_PT, y * MM_PER_PT

        self.slot_xy = [centre(r, c) for r, c in self.slots]
        self.split = SCREEN_W_PT * MM_PER_PT / 2

        n = len(SYMBOLS)
        self.xs = np.zeros(n)
        self.ys = np.zeros(n)
        self.pw = np.full(n, self.pitch_w)
        self.ph = np.full(n, self.pitch_h)
        self.lp = np.zeros(n)
        # fixed punctuation on the grid
        for (r, c), ch in fixed.items():
            if ch in SYM_INDEX:
                i = SYM_INDEX[ch]
                self.xs[i], self.ys[i] = centre(r, c)
        # long-press punctuation rides its host
        if family == '10col':
            self._tie(',', '.')
        else:
            self._tie(',', '.')
            self._tie("'", '-')
        # space on the bottom row
        bottom_y = INSET_TOP + 3 * (rh + ROW_GAP) + rh / 2
        if family == '10col':
            # 5 equal keys of weight 2: space is key 4 of 5
            usable = SCREEN_W_PT - INSET_LEFT - INSET_RIGHT - 4 * CELL_GAP
            w = usable / 5
            x = INSET_LEFT + 3 * (w + CELL_GAP) + w / 2
            sp_w = w
        else:
            weights = [1.2, 1.2, 1.2, 2.6, 1.2, 1.6]
            usable = SCREEN_W_PT - INSET_LEFT - INSET_RIGHT - 5 * CELL_GAP
            tot = sum(weights)
            x_cur = INSET_LEFT
            x, sp_w = 0.0, 0.0
            for i, wt in enumerate(weights):
                w = usable * wt / tot
                if i == 3:
                    x, sp_w = x_cur + w / 2, w
                x_cur += w + CELL_GAP
        i = SYM_INDEX[' ']
        self.xs[i] = x * MM_PER_PT
        self.ys[i] = bottom_y * MM_PER_PT
        self.pw[i] = (sp_w + CELL_GAP) * MM_PER_PT

    def _tie(self, host, rider):
        hi, ri = SYM_INDEX[host], SYM_INDEX[rider]
        self.xs[ri], self.ys[ri] = self.xs[hi], self.ys[hi]
        self.lp[ri] = LONGPRESS_MS

    def arrays(self, letters: list[str], perm: list[int]):
        """Positions for letters[i] at slot perm[i]; returns model arrays."""
        xs, ys, lp = self.xs.copy(), self.ys.copy(), self.lp.copy()
        for li, si in enumerate(perm):
            i = SYM_INDEX[letters[li]]
            xs[i], ys[i] = self.slot_xy[si]
        if self.family == '8col':
            for host, hidden in LP_8_LETTERS.items():
                hi, ri = SYM_INDEX[host], SYM_INDEX[hidden]
                xs[ri], ys[ri] = xs[hi], ys[hi]
                lp[ri] = LONGPRESS_MS
        side = (xs >= self.split).astype(np.int64)
        return xs, ys, self.pw, self.ph, side, lp




def anneal(scorer, geom: SlotGeometry, letters: list[str], *,
           w_two=0.5, w_one=0.5, iters=30000, restarts=4, seed=1,
           init_perm: list[int] | None = None, verbose=True):
    rng = random.Random(seed)
    n = len(letters)
    assert n <= len(geom.slots)

    def energy(perm):
        xs, ys, pw, ph, side, lp = geom.arrays(letters, perm)
        e, _, _ = scorer.score(xs, ys, pw, ph, side, lp, w_two, w_one)
        return e

    best_perm, best_e = None, math.inf
    for r in range(restarts):
        perm = list(init_perm) if init_perm else rng.sample(range(len(geom.slots)), n)
        if init_perm and r > 0:
            for _ in range(6):  # jitter later restarts
                i, j = rng.randrange(n), rng.randrange(n)
                perm[i], perm[j] = perm[j], perm[i]
        e = energy(perm)
        t0, t1 = e * 0.03, e * 0.0004
        for it in range(iters):
            t = t0 * (t1 / t0) ** (it / iters)
            i, j = rng.randrange(n), rng.randrange(n)
            if i == j:
                continue
            perm[i], perm[j] = perm[j], perm[i]
            e2 = energy(perm)
            if e2 < e or rng.random() < math.exp((e - e2) / t):
                e = e2
            else:
                perm[i], perm[j] = perm[j], perm[i]
        if e < best_e:
            best_e, best_perm = e, list(perm)
        if verbose:
            print(f'  restart {r}: {e:.2f} ms/char (best {best_e:.2f})')
    return best_perm, best_e


def greedy_swaps(scorer, geom: SlotGeometry, letters: list[str],
                 start_perm: list[int], *, w_two=0.5, w_one=0.5,
                 max_swaps=4, min_gain=0.012, validate=None,
                 validate_min_gain=0.005):
    """Hill-climb from a given assignment, keeping only clearly-paying swaps.

    Used for the 'stay close to Colemak' variant: each accepted swap must
    improve the approximate blended objective by at least min_gain, AND be
    confirmed by `validate(perm) -> exact blended ms/char` (if given) to
    improve the exact simulation by validate_min_gain — this filters out
    approximation noise so we never suggest a relearning cost that the full
    model can't cash.
    """
    def energy(perm):
        xs, ys, pw, ph, side, lp = geom.arrays(letters, perm)
        return scorer.score(xs, ys, pw, ph, side, lp, w_two, w_one)[0]

    perm = list(start_perm)
    e = energy(perm)
    e_exact = validate(perm) if validate else None
    swaps = []
    for _ in range(max_swaps):
        ranked = []
        for i in range(len(letters)):
            for j in range(i + 1, len(letters)):
                perm[i], perm[j] = perm[j], perm[i]
                gain = (e - energy(perm)) / e
                perm[i], perm[j] = perm[j], perm[i]
                if gain > min_gain:
                    ranked.append((gain, i, j))
        ranked.sort(reverse=True)
        accepted = False
        for gain, i, j in ranked[:5]:
            perm[i], perm[j] = perm[j], perm[i]
            if validate:
                e2_exact = validate(perm)
                if (e_exact - e2_exact) / e_exact < validate_min_gain:
                    perm[i], perm[j] = perm[j], perm[i]
                    continue
                e_exact = e2_exact
            e = energy(perm)
            swaps.append((letters[i], letters[j], gain))
            accepted = True
            break
        if not accepted:
            break
    return perm, e, swaps
