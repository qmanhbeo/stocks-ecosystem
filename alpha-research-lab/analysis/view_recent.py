"""
view_recent.py -- Quick result browser for FPT signal experiments.

Usage:
    python view_recent.py              # Last 5 experiments
    python view_recent.py --n 10       # Last 10
    python view_recent.py --best       # Top 5 by val edge over naive drift
    python view_recent.py --all        # Full history
"""
import argparse
import json
import sys


def load_results(filepath="results_summary.jsonl"):
    results = []
    try:
        with open(filepath, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    results.append(json.loads(line))
    except FileNotFoundError:
        print(f"No results file at: {filepath}")
        sys.exit(1)
    return results


def fmt(v, fmt_str, fallback="  n/a"):
    if v is None or (v != v):  # None or nan
        return fallback
    return fmt_str.format(v)


def print_table(results, total, label):
    print("\n" + "=" * 108)
    print("  {}  ({} shown of {} total)".format(label, len(results), total))
    print("=" * 108)
    print("  {:<18} {:<26} {:<18} {:>8} {:>8} {:>10} {:>10}".format(
        "ts", "name", "model", "val_dir", "edge", "pval_naive", "test_edge"
    ))
    print("  " + "-" * 104)
    for r in results:
        v = r["val"]
        edge = v.get("edge")
        pval_n = v.get("pval_naive")
        edge_str = fmt(edge, "{:+.2f}%")
        pval_str = fmt(pval_n, "{:.4f}")
        sig = "**" if (pval_n is not None and pval_n < 0.05) else "  "
        t = r.get("test")
        test_edge = fmt(t.get("edge") if t else None, "{:+.2f}%", "  SACRED")
        print("  {:<18} {:<26} {:<18} {:>7.2f}% {:>8} {:>9}{} {:>10}".format(
            r["ts"], r["name"], r["model"],
            v["dir"] * 100,
            edge_str, pval_str, sig, test_edge,
        ))
    print()


def show_recent(n):
    results = load_results()
    print_table(results[-n:], len(results), f"RECENT {n} EXPERIMENTS")


def show_best(n):
    results = load_results()
    key = lambda r: r["val"].get("edge", r["val"]["dir"] - r["val"].get("naive_dir", 0.5))
    print_table(sorted(results, key=key, reverse=True)[:n], len(results),
                f"TOP {n} BY VAL EDGE OVER NAIVE DRIFT")


def show_all():
    results = load_results()
    print_table(results, len(results), "ALL EXPERIMENTS")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=5)
    parser.add_argument("--best", action="store_true")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()
    if args.best:
        show_best(args.n)
    elif args.all:
        show_all()
    else:
        show_recent(args.n)
