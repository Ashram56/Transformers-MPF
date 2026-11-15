#!/usr/bin/env python3
"""The rules test bench (docs/test_bench.md): run it before pushing a rules change.

  scripts/bench.py                     every bench test: the modes, the adjustments, players, stress games, traces
  scripts/bench.py megatron wizard     only tests/bench/test_megatron.py and test_wizard.py
  scripts/bench.py --quick             without the stress games and the reference traces (about a minute)
  scripts/bench.py --stress 50         50 stress games of each kind instead of 2 (--seed N: first seed, default 1)
  scripts/bench.py --replay two_players_seed_1101 --seed 1000 --stress 25
                                       one stress game again, with its last actions printed
  scripts/bench.py --update-baseline   record how far the game matches the ROM's reference traces today
                                       (tests/bench/trace_baseline.json): after a change that matches them better

Anything after `--` goes to pytest (e.g. `-- -x -k adj_68`).
"""
import argparse
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BENCH = os.path.join("tests", "bench")


def update_baseline():
    sys.path.insert(0, ROOT)
    from concurrent.futures import ThreadPoolExecutor
    from tests.bench import traces
    names = traces.scenarios()
    old = traces.load_baseline() if os.path.exists(traces.BASELINE) else {}
    with ThreadPoolExecutor(max(1, min(4, os.cpu_count() or 1))) as pool:
        results = dict(zip(names, pool.map(traces.run, names)))
    worse, better = [], []
    for name in names:
        w, b = traces.compare(name, results[name], old.get(name, {}))
        worse += w
        better += b
    for line in better:
        print("better:", line)
    for line in worse:
        print("WORSE: ", line)
    traces.save_baseline(results)
    print("{} scenarios written to {} ({} better, {} worse)".format(
        len(names), os.path.relpath(traces.BASELINE, ROOT), len(better), len(worse)))
    return 1 if worse else 0


def main():
    argv = sys.argv[1:]
    extra = []
    if "--" in argv:
        extra = argv[argv.index("--") + 1:]
        argv = argv[:argv.index("--")]
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("names", nargs="*", help="bench files to run (megatron, battles, optimus, wizard, features, "
                                             "game_flow, adjustments, multiplayer, stress, traces); default all")
    ap.add_argument("--quick", action="store_true", help="skip the stress games and the reference traces")
    ap.add_argument("--stress", type=int, metavar="GAMES", help="stress games of each kind (default 2)")
    ap.add_argument("--seed", type=int, help="first stress seed (default 1)")
    ap.add_argument("--replay", metavar="TEST", help="run one stress game again (the name pytest printed)")
    ap.add_argument("--update-baseline", action="store_true", help="rewrite tests/bench/trace_baseline.json")
    args = ap.parse_args(argv)
    if args.update_baseline:
        return update_baseline()
    env = dict(os.environ)
    if args.stress:
        env["TF_BENCH_GAMES"] = str(args.stress)
    if args.seed is not None:
        env["TF_BENCH_SEED"] = str(args.seed)
    cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"]
    if args.replay:
        cmd += [os.path.join(BENCH, "test_stress.py"), "-s", "-k", args.replay]
    elif args.names:
        cmd += [os.path.join(BENCH, "test_{}.py".format(name)) for name in args.names]
    else:
        cmd.append(BENCH)
        if args.quick:
            cmd += ["--deselect", os.path.join(BENCH, "test_stress.py"),
                    "--deselect", os.path.join(BENCH, "test_traces.py")]
    return subprocess.call(cmd + extra, cwd=ROOT, env=env)


if __name__ == "__main__":
    sys.exit(main())
