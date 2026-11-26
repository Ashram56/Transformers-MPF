"""Walk the service menu in tf_180's code and record every screen (rom/rom_data/settings/service_screens.json).

Runs the ROM in the scenario runner (scenario_lift.py: the ROM's own code in Unicorn, factory settings), starts
the machine, presses SELECT (152) and walks every menu as an operator would: PLUS (151) to the next item until
the first one comes back, SELECT on each item, PLUS through the item's screens (audits, adjustments, tests; at
most 60 per item), BACK (149) out. Each screen keeps the texts the ROM drew 0.9 s after the press (text, font,
flags, x, y), as the deff runner records them. The menu engine is 0x0000eb3c (lists 0x00030d04 / 0x00030cf8),
the service deff deff_003 [0x0103f960] started by start_deff_3 [0x0000ed90].

Usage: TF_ROM=tf_180.bin service_walk.py OUT.json   (about 15 minutes)
"""
import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scenario_lift, switch_lift, deff_lift  # noqa: E402
from scenario_lift import ticks  # noqa: E402
deff_lift.work_pages()
SEL, PLUS, BACK = 152, 151, 149
DRAW = ('text', 'fill', 'copy_rect', 'invert', 'show', 'remap', 'panel', 'dissolve', 'sound', 'leff')
r = scenario_lift.ScenarioRunner()
switch_lift.start_game(r)
r.auto = 0
r.step(r.now + 30)
out = sys.argv[1]
screens = []
cur = {}

def look(wait=0.9):
    r.ops = []
    r.step(r.now + ticks(wait))
    last = {}
    for o in r.ops:
        if o['op'] == 'text':
            last[(o.get('x'), o.get('y'), o.get('page'))] = o
    texts = sorted(last.values(), key=lambda o: (o.get('y') or 0, o.get('x') or 0))
    cur['texts'] = [{k: o.get(k) for k in ('text', 'font', 'flags', 'x', 'y')} for o in texts]
    cur['ops'] = [o for o in r.ops if o['op'] in DRAW][-60:]
    seen = []
    for t in cur['texts']:
        if t['text'] not in seen:
            seen.append(t['text'])
    cur['key'] = tuple(seen)
    return cur['key']

def press(sw, path):
    r.pulse(sw, 100)
    k = look()
    screens.append({'path': path, 'button': {SEL: 'SELECT', PLUS: 'PLUS', BACK: 'BACK'}[sw], 'tick': r.now,
                    'texts': cur['texts'], 'ops': cur['ops']})
    print(path, '|', ' / '.join(k)[:150], flush=True)
    return k

HOW = ("rom/tools/service_walk.py: the service menu walked in ROM code (code run, factory settings): SELECT (152) "
       "from attract, PLUS (151) through each menu until its first item repeats, SELECT on each item, PLUS through "
       "the item's screens (at most 60), BACK (149). Each screen lists the texts the ROM drew (text, font, flags, "
       "x, y) 0.9 s after the press.")


def save():
    doc = {"rom": "tf_180", "how": HOW, "tick_ms": 16.0,
           "screens": [{k: x[k] for k in ("path", "button", "tick", "texts")} for x in screens]}
    with open(out, "w") as f:
        json.dump(doc, f, indent=0)

def items_of(first, path, cap=40):
    """The menu's runtime list: PLUS until the first item comes back."""
    lst = [first]
    for _ in range(cap):
        k = press(PLUS, path + ' [list]')
        if k == first:
            return lst
        lst.append(k)
    return lst

def goto(lst, i, path):
    """Back on item i of this menu after a BACK: PLUS around the list until it shows."""
    for _ in range(len(lst) + 1):
        k = cur['key']
        if k == lst[i]:
            return True
        if k not in lst:
            return False
        press(PLUS, path + ' [resync]')
    return False

def walk(first, path, depth=0):
    lst = items_of(first, path)
    for i, it in enumerate(lst):
        if not goto(lst, i, path):
            print('LOST at', path, it, flush=True)
            return False
        name = ' '.join(it)
        here = path + ' / ' + name
        if name.startswith(('RETURN TO', 'EXIT SERVICE')):
            continue
        k = press(SEL, here + ' [select]')
        if name.startswith('GO TO ') and depth < 4 and k and k != it:
            ok = walk(k, here, depth + 1)
            save()
            if cur['key'] == it:           # a BACK inside the sub-menu already brought us back here
                continue
        elif k != it:
            seen = {k}
            for n in range(60):            # entries of the screen (audits, adjustments, tests): PLUS until a repeat
                k2 = press(PLUS, here + ' [+%d]' % (n + 1))
                if k2 in seen:
                    break
                seen.add(k2)
        if cur['key'] != it:
            press(BACK, here + ' [back]')
        save()
    return True

press(SEL, 'title')
k = press(SEL, 'MAIN MENU')
walk(k, 'MAIN MENU')
save()
print('done', len(screens))
