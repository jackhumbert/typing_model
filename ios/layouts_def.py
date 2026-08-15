"""Layout definitions and slot machinery for the iOS thumb-typing explorer.

Two geometry families on the iPhone 16 portrait board (same insets/gaps as the
uploaded Colemak Ortho .xkeyboard):

* 10-column ortho — the uploaded board: 5.5 x 7.1 mm keys (6.5 mm pitch).
  Below the ~7.7 mm serial-tap precision threshold (Parhi et al. 2006).
* 8-column — 7.1 x 7.1 mm keys (8.1 mm pitch), clearing the threshold.
  26 letters no longer fit on 3 rows, so the 4 rarest (q z x j, together
  ~0.5% of letters) move to long-press candidates on mnemonic hosts:
  q on u (q is followed by u 99% of the time), z on s, x on c, j on g.

Bottom row of the 10-col family is exactly the user's current one:
[123] [bksp] [#+=] [space] [return].  The 8-col family adds shift bottom-left
(its stock-iOS position) since the grid no longer has a spare corner for it.
"""

from __future__ import annotations

from thumbmodel import Layout, make_grid_layout

LETTERS = 'abcdefghijklmnopqrstuvwxyz'
SYMBOLS = LETTERS + " ',.-"

BOTTOM_10 = [('1', 2.0), ('⌫', 2.0), ('#', 2.0), (' ', 2.0), ('⏎', 2.0)]
BOTTOM_8 = [('^', 1.2), ('1', 1.2), ('⌫', 1.2), (' ', 2.6), ('#', 1.2), ('⏎', 1.6)]

LP_10 = {',': ['.']}           # as in the uploaded board (plus @/_ we don't score)
LP_8_PUNCT = {',': ['.'], "'": ['-']}
LP_8_LETTERS = {'u': 'q', 's': 'z', 'c': 'x', 'g': 'j'}  # host -> hidden letter


def colemak_ortho() -> Layout:
    return make_grid_layout(
        'Colemak Ortho (current)',
        ['qwfpgjluy^', 'arstdhneio', "zxcvbkm,'-"],
        bottom=BOTTOM_10, longpress=LP_10,
        meta={'family': '10col', 'source': 'uploaded'},
    )


def qwerty_ortho() -> Layout:
    return make_grid_layout(
        'QWERTY ortho (reference)',
        ['qwertyuiop', 'asdfghjkl^', "zxcvbnm,'-"],
        bottom=BOTTOM_10, longpress=LP_10,
        meta={'family': '10col', 'source': 'reference'},
    )


# ---- slot machinery for the optimizer ------------------------------------

# 10-col: 26 letter slots (30 grid cells minus shift and the three punct keys)
SLOTS_10 = [(r, c) for r in range(3) for c in range(10)
            if not (r == 0 and c == 9)      # shift
            and not (r == 2 and c >= 7)]    # , ' -
FIXED_10 = {(0, 9): '^', (2, 7): ',', (2, 8): "'", (2, 9): '-'}

# 8-col: 22 tap slots for letters (24 cells minus , and ')
SLOTS_8 = [(r, c) for r in range(3) for c in range(8)
           if not (r == 2 and c >= 6)]      # , '
FIXED_8 = {(2, 6): ',', (2, 7): "'"}
TAP_LETTERS_8 = [c for c in LETTERS if c not in LP_8_LETTERS.values()]  # 22


def assignment_to_rows(assignment: dict, n_cols: int, fixed: dict) -> list[str]:
    rows = [['∅'] * n_cols for _ in range(3)]
    for (r, c), ch in fixed.items():
        rows[r][c] = ch
    for (r, c), ch in assignment.items():
        rows[r][c] = ch
    return [''.join(r) for r in rows]


def layout_from_assignment(name: str, assignment: dict, family: str,
                           meta: dict | None = None) -> Layout:
    m = {'family': family}
    m.update(meta or {})
    if family == '10col':
        rows = assignment_to_rows(assignment, 10, FIXED_10)
        return make_grid_layout(name, rows, bottom=BOTTOM_10, longpress=LP_10,
                                meta=m)
    rows = assignment_to_rows(assignment, 8, FIXED_8)
    lp = dict(LP_8_PUNCT)
    for host, hidden in LP_8_LETTERS.items():
        lp.setdefault(host, []).append(hidden)
    return make_grid_layout(name, rows, bottom=BOTTOM_8, longpress=lp, meta=m)


def colemak_assignment_10() -> dict:
    rows = ['qwfpgjluy^', 'arstdhneio', "zxcvbkm,'-"]
    out = {}
    for r, row in enumerate(rows):
        for c, ch in enumerate(row):
            if (r, c) in FIXED_10:
                continue
            out[(r, c)] = ch
    return out


def render_ascii(layout: Layout) -> str:
    lines = []
    for row in layout.grid:
        lines.append('  ' + ' '.join(f'{c if c != "∅" else "·"}' for c in row))
    lines.append('  [' + '] ['.join(layout.bottom) + ']')
    return '\n'.join(lines)
