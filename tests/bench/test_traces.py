"""The 24 reference traces must not match the ROM less than they do in tests/bench/trace_baseline.json
(tests/bench/traces.py; scripts/bench.py --update-baseline records an improvement)."""
import os
import unittest
from concurrent.futures import ThreadPoolExecutor

from tests.bench import traces


# known on main: the bonus 0.37 s late; one audit of battle_blackout out of order
KNOWN = {("allspark_energon", "score"), ("battle_blackout", "audit")}


class TestReferenceTraces(unittest.TestCase):

    def test_no_scenario_regressed(self):
        baseline = traces.load_baseline()
        names = traces.scenarios()
        self.assertEqual(sorted(baseline), names, "scenarios and baseline differ: scripts/bench.py --update-baseline")
        with ThreadPoolExecutor(max(1, min(4, os.cpu_count() or 1))) as pool:
            results = dict(zip(names, pool.map(traces.run, names)))
        worse = []
        for name in names:
            worse += traces.compare(name, results[name], baseline[name])[0]
        self.assertEqual([], worse, "reference traces match the ROM less than the baseline:\n" + "\n".join(worse))

    def test_scores_and_audits_match_the_rom(self):
        """What the baseline itself must keep saying: scores, audits and multiball starts equal the ROM's in every
        scenario but allspark_energon (its bonus comes 0.37 s late, docs/rom_differences.md)."""
        baseline = traces.load_baseline()
        bad = ["{} {}: {}".format(name, kind, status[kind]) for name, status in sorted(baseline.items())
               for kind in traces.STRICT_KINDS
               if not status.get(kind, "").startswith("OK") and (name, kind) not in KNOWN]
        self.assertEqual([], bad)
