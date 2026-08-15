"""Generate .xkeyboard archives (XKeyboard iOS app) from layout specs.

Strategy: build the letters layer from scratch following the exact schema of
the uploaded Colemak Ortho board, and carry over the numbers/symbols layers
from the original archive with every UUID consistently regenerated (so
variants can be installed side by side without identifier collisions).
"""

from __future__ import annotations

import copy
import datetime
import plistlib
import re
import uuid
import zipfile


UUID_RE = re.compile(r'^[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}$')


def new_uuid() -> str:
    return str(uuid.uuid4()).upper()


class UuidMap:
    def __init__(self):
        self.map: dict[str, str] = {}

    def get(self, old: str) -> str:
        if old not in self.map:
            self.map[old] = new_uuid()
        return self.map[old]

    def remap(self, obj):
        if isinstance(obj, dict):
            return {self.remap(k): self.remap(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self.remap(v) for v in obj]
        if isinstance(obj, str) and UUID_RE.match(obj):
            return self.get(obj)
        return obj


SHIFT_CAPS = {',': '!', "'": '"', '-': '?', '.': '?'}


def _key(text: str, output: str | None = None, *, icon: int | None = None,
         ktype: int | None = None) -> dict:
    kid = new_uuid()
    cap = {'icon': icon} if icon is not None else {'text': text}
    k = {'keyCap': cap, 'keyID': kid}
    if output is not None:
        k['output'] = output
    if ktype is not None:
        k['type'] = ktype
    return k


def _letter_cell(ch: str, *, candidates: list[str] | None = None) -> dict:
    cell_id = new_uuid()
    key = _key(ch, ch)
    key['keyID'] = cell_id  # original file: base keyID == cellID
    cell = {'cellID': cell_id, 'key': key}
    shift_out = SHIFT_CAPS.get(ch, ch.upper())
    cell['shiftKey'] = _key(shift_out, shift_out)
    if candidates:
        cell['candidateKeys'] = [_key(c, c) for c in candidates]
        shift_cands = [SHIFT_CAPS.get(c, c.upper()) for c in candidates
                       if c.isalpha()]
        if shift_cands:
            cell['shiftCandidateKeys'] = [_key(c, c) for c in shift_cands]
    return cell


def _special_cell(ch: str, layer_ids: dict[str, str]) -> dict:
    cell_id = new_uuid()
    if ch == '^':
        key = _key('', icon=2, ktype=3)
    elif ch == '⌫':
        key = _key('', icon=3, ktype=4)
    elif ch == '1':
        key = _key('123', layer_ids['numbers'], ktype=5)
    elif ch == '#':
        key = _key('#+=', layer_ids['symbols'], ktype=5)
    elif ch == ' ':
        key = _key('', ' ', ktype=1)
    elif ch == '⏎':
        key = _key('', '\n', icon=7, ktype=2)
    else:
        raise ValueError(f'unknown special key {ch!r}')
    key['keyID'] = cell_id
    return {'cellID': cell_id, 'key': key}


def build_letters_layer(rows: list[str], bottom: list[tuple[str, float]],
                        longpress: dict[str, list[str]],
                        layer_ids: dict[str, str]) -> dict:
    cells = []
    layout_rows = []
    layout_map = {}

    def add_row(specs: list[tuple[str, float]]):
        row_cells = []
        for ch, weight in specs:
            if ch == '∅':
                continue
            if ch.isalpha() and ch.islower() or ch in ",'-.":
                cell = _letter_cell(ch, candidates=longpress.get(ch))
            else:
                cell = _special_cell(ch, layer_ids)
            cells.append(cell)
            rc_id = new_uuid()
            layout_map[rc_id] = cell['cellID']
            row_cells.append({'cellID': rc_id, 'floatType': 0, 'weight': weight})
        layout_rows.append({
            'alignment': 0,
            'cells': row_cells,
            'cellsWeight': sum(c['weight'] for c in row_cells),
            'weight': 1.0,
        })

    for row in rows:
        add_row([(ch, 1.0) for ch in row])
    add_row(list(bottom))

    control = {
        'cells': cells,
        'controlID': new_uuid(),
        'controlType': 'keyPad',
        'layout': {
            'autoModel': True,
            'cellGap': 6.0,
            'contentInset': '8,3,3,3',
            'layoutType': 'Standard',
            'rowGap': 11.0,
            'rows': layout_rows,
        },
        'layoutMap': layout_map,
    }
    section_id = new_uuid()
    outer_cell = new_uuid()
    return {
        'layerID': layer_ids['letters'],
        'layout': {'autoModel': True, 'cell': {'cellID': outer_cell},
                   'layoutType': 'One'},
        'layoutMap': {outer_cell: section_id},
        'sections': [{
            'layers': [{'control': control, 'layerID': new_uuid()}],
            'sectionID': section_id,
        }],
    }


def generate(original_path: str, out_path: str, *, name: str,
             rows: list[str], bottom: list[tuple[str, float]],
             longpress: dict[str, list[str]]):
    with zipfile.ZipFile(original_path) as z:
        board = plistlib.loads(z.read('Board_iPhone_Portrait.plist'))
        keyboard = plistlib.loads(z.read('Keyboard.plist'))
        assets = {n: z.read(n) for n in z.namelist() if n.startswith('Assets/')}

    old_layers = board['panel']['layers']
    old_ids = [ly['layerID'] for ly in old_layers]  # letters, numbers, symbols

    umap = UuidMap()
    layer_ids = {
        'letters': umap.get(old_ids[0]),
        'numbers': umap.get(old_ids[1]),
        'symbols': umap.get(old_ids[2]),
    }
    letters = build_letters_layer(rows, bottom, longpress, layer_ids)
    numbers = umap.remap(copy.deepcopy(old_layers[1]))
    symbols = umap.remap(copy.deepcopy(old_layers[2]))

    new_board = {
        'deviceType': board.get('deviceType', 1),
        'heightRatio': board.get('heightRatio', 1.0),
        'isLandscape': False,
        'panel': {'layers': [letters, numbers, symbols],
                  'panelID': new_uuid()},
    }
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    new_keyboard = dict(keyboard)
    new_keyboard.update({
        'keyboardID': new_uuid(),
        'name': name,
        'createDateTime': now,
        'updateDateTime': now,
    })

    with zipfile.ZipFile(out_path, 'w', zipfile.ZIP_DEFLATED) as z:
        for member, data in assets.items():
            z.writestr(member, data)
        z.writestr('Board_iPhone_Portrait.plist', plistlib.dumps(new_board))
        z.writestr('Keyboard.plist', plistlib.dumps(new_keyboard))
