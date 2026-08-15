"""Thumb-typing effort model for iPhone soft keyboards.

Adapts the carpalx-style corpus->effort approach of this repo (index.html) to
touchscreen thumb typing, replacing finger/homerow assignments with movement
models from the mobile text-entry literature:

* One-thumb + same-side taps: quadratic-in-ID Fitts variant fitted for thumbs
  by Oulasvirta et al., "Improving Two-Thumb Text Entry on Touchscreen
  Devices" (CHI 2013, the KALQ paper), Eq. 3-4.
* Alternating (two-thumb) taps: bivariate model in ID and elapsed wait time
  from the same paper, Eq. 5-6 (hover-over behaviour: the idle thumb pre-moves
  to its next target; long waits carry a big penalty).
* Movement amplitude/target size use the Shannon form ID = log2(D/W + 1)
  (MacKenzie), with W taken as the directional key pitch.
* Precision: bivariate-Gaussian tap scatter (sigma ~2 mm, cf. Azenkot & Zhai
  MobileHCI 2012; Bi, Li & Zhai's FFitts law) integrated over the key's
  Voronoi cell -> per-tap miss risk. Since this keyboard has no autocorrect,
  miss risk is the precision currency.

All times in ms, all distances in mm.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

import numpy as np

# ---------------------------------------------------------------- geometry

# iPhone 16 portrait: 393 pt logical width, 6.1" 19.5:9 panel -> 65.1 mm wide.
SCREEN_W_PT = 393.0
MM_PER_PT = 65.1 / SCREEN_W_PT

# Values read straight from Board_iPhone_Portrait.plist of the uploaded file.
INSET_TOP, INSET_LEFT, INSET_BOTTOM, INSET_RIGHT = 8.0, 3.0, 3.0, 3.0
CELL_GAP = 6.0
ROW_GAP = 11.0
BOARD_H_PT = 216.0  # standard iOS keyboard key area height (heightRatio=1.0)
N_ROWS = 4          # 3 letter rows + bottom function row


def row_height_pt(n_rows: int = N_ROWS) -> float:
    usable = BOARD_H_PT - INSET_TOP - INSET_BOTTOM - (n_rows - 1) * ROW_GAP
    return usable / n_rows


def key_width_pt(n_cols: int) -> float:
    usable = SCREEN_W_PT - INSET_LEFT - INSET_RIGHT - (n_cols - 1) * CELL_GAP
    return usable / n_cols


# ---------------------------------------------------------------- key & layout

@dataclass
class Key:
    char: str            # the character this key produces (lowercase)
    x: float             # centre x in mm
    y: float             # centre y in mm
    w: float             # visible key width in mm
    h: float             # visible key height in mm
    pitch_w: float       # width of the key's exclusive strip (w + gap) in mm
    pitch_h: float
    longpress_ms: float = 0.0  # extra hold time if char sits on a candidate key


@dataclass
class Layout:
    name: str
    n_cols: int
    keys: dict[str, Key] = field(default_factory=dict)
    grid: list[list[str]] = field(default_factory=list)   # letter rows for display
    bottom: list[str] = field(default_factory=list)
    meta: dict = field(default_factory=dict)

    @property
    def split_x(self) -> float:
        return SCREEN_W_PT * MM_PER_PT / 2.0

    def side(self, key: Key) -> int:
        """0 = left thumb, 1 = right thumb."""
        return 0 if key.x < self.split_x else 1


def make_grid_layout(name: str, rows: list[str], *, n_cols: int | None = None,
                     bottom: list[tuple[str, float]] | None = None,
                     longpress: dict[str, list[str]] | None = None,
                     meta: dict | None = None) -> Layout:
    """Build a Layout from letter-row strings.

    rows: list of strings, one char per key, e.g. "qwfpgjluy^" where
          '^' = shift (ignored for scoring), '␣' = space.
    bottom: list of (char, weight); default mirrors the uploaded board:
            123 / backspace / #+= / space / return, equal widths.
    longpress: host char -> list of chars reachable by long-press on it.
    """
    n_cols = n_cols or max(len(r) for r in rows)
    kw = key_width_pt(n_cols)
    rh = row_height_pt()
    lay = Layout(name=name, n_cols=n_cols, meta=meta or {})
    lay.grid = [list(r) for r in rows]

    def add(char, x_pt, y_pt, w_pt, h_pt, lp=0.0):
        lay.keys[char] = Key(
            char=char,
            x=x_pt * MM_PER_PT, y=y_pt * MM_PER_PT,
            w=w_pt * MM_PER_PT, h=h_pt * MM_PER_PT,
            pitch_w=(w_pt + CELL_GAP) * MM_PER_PT,
            pitch_h=(h_pt + ROW_GAP) * MM_PER_PT,
            longpress_ms=lp,
        )

    for ri, row in enumerate(rows):
        y = INSET_TOP + ri * (rh + ROW_GAP) + rh / 2
        for ci, ch in enumerate(row):
            if ch in ('^', '∅'):
                continue  # shift / empty: not scored
            x = INSET_LEFT + ci * (kw + CELL_GAP) + kw / 2
            add(ch, x, y, kw, rh)

    bottom = bottom or [('1', 2.0), ('⌫', 2.0), ('#', 2.0), (' ', 2.0), ('⏎', 2.0)]
    lay.bottom = [c for c, _ in bottom]
    total_w = sum(wt for _, wt in bottom)
    usable = SCREEN_W_PT - INSET_LEFT - INSET_RIGHT - (len(bottom) - 1) * CELL_GAP
    y = INSET_TOP + 3 * (rh + ROW_GAP) + rh / 2
    x_cursor = INSET_LEFT
    for ch, wt in bottom:
        w_pt = usable * wt / total_w
        if ch in (' ', '⌫'):
            add(ch, x_cursor + w_pt / 2, y, w_pt, rh)
        x_cursor += w_pt + CELL_GAP

    for host, extras in (longpress or {}).items():
        hk = lay.keys[host]
        for ch in extras:
            lay.keys[ch] = Key(char=ch, x=hk.x, y=hk.y, w=hk.w, h=hk.h,
                               pitch_w=hk.pitch_w, pitch_h=hk.pitch_h,
                               longpress_ms=LONGPRESS_MS)
    return lay


# ---------------------------------------------------------------- movement models

# KALQ (CHI 2013) Eq. 3/4: same-side thumb taps, MT(ID) polynomials.
# Left = non-dominant, right = dominant (30 ms faster on average).
def mt_same(id_: float, side: int) -> float:
    id_ = min(max(id_, 1.3), 5.0)
    if side == 0:
        return 319.5 - 89.0 * id_ + 36.7 * id_ * id_
    return 237.3 - 7.6 * id_ + 13.8 * id_ * id_


# KALQ Eq. 5/6: alternating taps, MT(ID, t_elapsed).  The idle thumb hovers
# toward its target; short waits are cheap (often cheaper than a same-side
# tap), waits beyond ~600 ms carry a rapidly growing penalty.
def mt_alt(id_: float, t_elapsed: float, side: int) -> float:
    id_ = min(max(id_, 1.3), 4.2)
    t = min(max(t_elapsed, 0.0), 1200.0)
    if side == 0:
        mt = (265.286 - 9.501 * id_ - 0.024 * t + 2.003 * id_ * id_
              - 0.007 * t * id_ + 3.322e-4 * t * t)
    else:
        mt = (142.601 + 86.564 * id_ + 0.062 * t - 17.949 * id_ * id_
              - 0.035 * t * id_ + 1.930e-4 * t * t)
    return max(mt, 110.0)


SAME_KEY_MS = 160.0     # repeat tap on the same key
LONGPRESS_MS = 350.0    # extra hold to open the candidate popup
FIRST_TAP_ID = 1.3      # cold-start tap


def shannon_id(d: float, w: float) -> float:
    return math.log2(d / w + 1.0) if d > 0 else 0.0


def directional_width(dx: float, dy: float, key: Key) -> float:
    """Approximate target width along the movement direction (ellipse model)."""
    d = math.hypot(dx, dy)
    if d == 0:
        return key.pitch_w
    c, s = dx / d, dy / d
    inv = math.sqrt((c / key.pitch_w) ** 2 + (s / key.pitch_h) ** 2)
    return 1.0 / inv


# ---------------------------------------------------------------- corpus

KEEP = set("abcdefghijklmnopqrstuvwxyz '.,-")
BREAK = '\x00'


def clean_text(text: str) -> str:
    text = text.lower()
    text = text.replace('’', "'").replace('‘', "'")
    text = text.replace('“', '').replace('”', '')
    text = re.sub(r'\s+', ' ', text)
    out = []
    for ch in text:
        out.append(ch if ch in KEEP else BREAK)
    return ''.join(out)


def load_corpus(paths_weights: list[tuple[str, int]]) -> str:
    parts = []
    for path, repeats in paths_weights:
        with open(path, encoding='utf-8') as f:
            parts.extend([clean_text(f.read())] * repeats)
    return BREAK.join(parts)


# ---------------------------------------------------------------- simulation

@dataclass
class Result:
    name: str
    ms_per_char_2t: float
    ms_per_char_1t: float
    wpm_2t: float
    wpm_1t: float
    travel_mm_per_tap: float
    mean_id: float
    alternation: float
    same_side_runs: float
    miss_pct: float
    longpress_pct: float
    coverage: float
    key_time: dict[str, float] = field(default_factory=dict)
    key_count: dict[str, float] = field(default_factory=dict)


def _phi(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def miss_probability(key: Key, sigma: float = 2.0) -> float:
    """P(tap outside the key's Voronoi cell), centred bivariate Gaussian."""
    px = _phi(key.pitch_w / 2 / sigma) - _phi(-key.pitch_w / 2 / sigma)
    py = _phi(key.pitch_h / 2 / sigma) - _phi(-key.pitch_h / 2 / sigma)
    return 1.0 - px * py


def simulate(layout: Layout, stream: str) -> Result:
    keys = layout.keys
    # --- exact two-thumb pass -------------------------------------------
    t2 = 0.0
    taps = 0
    travel = 0.0
    id_sum = 0.0
    alt_count = 0
    trans_count = 0
    lp_count = 0
    miss_sum = 0.0
    key_time: dict[str, float] = {}
    key_count: dict[str, float] = {}
    thumb_pos: list[Key | None] = [None, None]
    thumb_t: list[float] = [0.0, 0.0]
    prev_side = -1
    known = 0
    total_chars = 0
    miss_cache = {c: miss_probability(k) for c, k in keys.items()}

    for ch in stream:
        if ch == BREAK:
            prev_side = -1
            thumb_pos = [None, None]
            continue
        total_chars += 1
        key = keys.get(ch)
        if key is None:
            prev_side = -1
            continue
        known += 1

        def tap_cost(side_: int) -> tuple[float, float, float]:
            """(mt, id, travel) for pressing `key` with thumb side_."""
            origin = thumb_pos[side_]
            if origin is None:
                return mt_same(FIRST_TAP_ID, side_), 0.0, 0.0
            dx, dy = key.x - origin.x, key.y - origin.y
            d = math.hypot(dx, dy)
            if side_ == prev_side:
                if d < 1e-9:
                    return SAME_KEY_MS, 0.0, 0.0
                w = directional_width(dx, dy, key)
                id_ = shannon_id(d, w)
                return mt_same(id_, side_), id_, d
            w = directional_width(dx, dy, key) if d > 0 else key.pitch_w
            id_ = shannon_id(d, w)
            return mt_alt(id_, t2 - thumb_t[side_], side_), id_, d

        # pick thumb: fixed by side for letters; space may take either thumb
        if ch == ' ':
            costs = [tap_cost(0), tap_cost(1)]
            side = 0 if costs[0][0] <= costs[1][0] else 1
            mt, id_, d = costs[side]
        else:
            side = layout.side(key)
            mt, id_, d = tap_cost(side)
        id_sum += id_
        travel += d
        if prev_side >= 0:
            trans_count += 1
            if side != prev_side:
                alt_count += 1
        if key.longpress_ms > 0:
            mt += key.longpress_ms
            lp_count += 1
        t2 += mt
        taps += 1
        thumb_pos[side] = key
        thumb_t[side] = t2
        prev_side = side
        miss_sum += miss_cache[ch]
        key_time[ch] = key_time.get(ch, 0.0) + mt
        key_count[ch] = key_count.get(ch, 0.0) + 1

    # --- exact one-thumb pass -------------------------------------------
    t1 = 0.0
    last: Key | None = None
    for ch in stream:
        if ch == BREAK:
            last = None
            continue
        key = keys.get(ch)
        if key is None:
            last = None
            continue
        if last is None:
            mt = mt_same(FIRST_TAP_ID, 1)
        else:
            dx, dy = key.x - last.x, key.y - last.y
            d = math.hypot(dx, dy)
            if d < 1e-9:
                mt = SAME_KEY_MS
            else:
                w = directional_width(dx, dy, key)
                mt = mt_same(shannon_id(d, w), 1)
        if key.longpress_ms > 0:
            mt += key.longpress_ms
        t1 += mt
        last = key

    n = max(taps, 1)
    ms2 = t2 / n
    ms1 = t1 / n
    return Result(
        name=layout.name,
        ms_per_char_2t=ms2,
        ms_per_char_1t=ms1,
        wpm_2t=60000.0 / ms2 / 5.0,
        wpm_1t=60000.0 / ms1 / 5.0,
        travel_mm_per_tap=travel / n,
        mean_id=id_sum / n,
        alternation=alt_count / max(trans_count, 1),
        same_side_runs=1.0 - alt_count / max(trans_count, 1),
        miss_pct=100.0 * miss_sum / n,
        longpress_pct=100.0 * lp_count / n,
        coverage=known / max(total_chars, 1),
        key_time=key_time,
        key_count=key_count,
    )


# ------------------------------------------------- fast trigram objective

class TrigramScorer:
    """Vectorised approximate objective for annealing.

    Decomposes the stream into trigram counts. For a tap C preceded by B and
    A: if side(C)==side(B) it is a same-side move B->C; otherwise it is an
    alternating tap whose thumb last rested on A when side(A)==side(C) (the
    dominant ABA pattern), else on C's own home (cold hover), with t_elapsed
    approximated by a constant mean interval. One-thumb time decomposes over
    bigrams exactly.
    """

    # Mean inter-press interval at realistic expert pace (exact sim shows
    # ~310 ms/char); the alternating-tap wait penalty is evaluated here.
    T_ELAPSED_MEAN = 310.0

    def __init__(self, stream: str, symbols: str):
        self.symbols = symbols
        index = {c: i for i, c in enumerate(symbols)}
        counts: dict[tuple[int, int, int], int] = {}
        big: dict[tuple[int, int], int] = {}
        a = b = None
        for ch in stream:
            i = index.get(ch)
            if ch == BREAK or i is None:
                a = b = None
                continue
            if b is not None:
                big[(b, i)] = big.get((b, i), 0) + 1
                if a is not None:
                    counts[(a, b, i)] = counts.get((a, b, i), 0) + 1
            a, b = b, i
        self.tri = np.array([(k[0], k[1], k[2], v) for k, v in counts.items()],
                            dtype=np.float64)
        self.bi = np.array([(k[0], k[1], v) for k, v in big.items()],
                           dtype=np.float64)

    def score(self, xs, ys, pw, ph, side, lp, w_two=0.5, w_one=0.5):
        """xs/ys/pw/ph/side/lp: arrays indexed by symbol id."""
        # --- one-thumb over bigrams
        b0 = self.bi[:, 0].astype(int)
        b1 = self.bi[:, 1].astype(int)
        cnt = self.bi[:, 2]
        dx = xs[b1] - xs[b0]
        dy = ys[b1] - ys[b0]
        d = np.hypot(dx, dy)
        with np.errstate(divide='ignore', invalid='ignore'):
            inv = np.sqrt((dx / d / pw[b1]) ** 2 + (dy / d / ph[b1]) ** 2)
            wdir = np.where(d > 0, 1.0 / inv, pw[b1])
        id_ = np.log2(d / wdir + 1.0, where=d > 0, out=np.zeros_like(d))
        idc = np.clip(id_, 1.3, 5.0)
        mt1 = 237.3 - 7.6 * idc + 13.8 * idc * idc
        mt1 = np.where(d < 1e-9, SAME_KEY_MS, mt1) + lp[b1]
        one = float((mt1 * cnt).sum() / cnt.sum())

        # --- two-thumb over trigrams
        t0 = self.tri[:, 0].astype(int)
        t1_ = self.tri[:, 1].astype(int)
        t2_ = self.tri[:, 2].astype(int)
        tc = self.tri[:, 3]
        same = side[t2_] == side[t1_]
        # same-side: move from B; alternating: move from A if A on same side
        ox = np.where(same, xs[t1_], np.where(side[t0] == side[t2_], xs[t0], xs[t2_]))
        oy = np.where(same, ys[t1_], np.where(side[t0] == side[t2_], ys[t0], ys[t2_]))
        dx = xs[t2_] - ox
        dy = ys[t2_] - oy
        d = np.hypot(dx, dy)
        with np.errstate(divide='ignore', invalid='ignore'):
            inv = np.sqrt((dx / d / pw[t2_]) ** 2 + (dy / d / ph[t2_]) ** 2)
            wdir = np.where(d > 0, 1.0 / inv, pw[t2_])
        id_ = np.log2(d / wdir + 1.0, where=d > 0, out=np.zeros_like(d))
        s = side[t2_]
        idc_s = np.clip(id_, 1.3, 5.0)
        mt_s = np.where(s == 0,
                        319.5 - 89.0 * idc_s + 36.7 * idc_s * idc_s,
                        237.3 - 7.6 * idc_s + 13.8 * idc_s * idc_s)
        mt_s = np.where(d < 1e-9, SAME_KEY_MS, mt_s)
        te = self.T_ELAPSED_MEAN
        idc_a = np.clip(id_, 1.3, 4.2)
        mt_a = np.where(
            s == 0,
            265.286 - 9.501 * idc_a - 0.024 * te + 2.003 * idc_a ** 2
            - 0.007 * te * idc_a + 3.322e-4 * te * te,
            142.601 + 86.564 * idc_a + 0.062 * te - 17.949 * idc_a ** 2
            - 0.035 * te * idc_a + 1.930e-4 * te * te)
        mt_a = np.maximum(mt_a, 110.0)
        mt2 = np.where(same, mt_s, mt_a) + lp[t2_]
        two = float((mt2 * tc).sum() / tc.sum())
        return w_two * two + w_one * one, two, one
