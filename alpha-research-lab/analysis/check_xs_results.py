import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

with open('xs_wf_results.jsonl') as f:
    records = [json.loads(l) for l in f if l.strip()]

# Show X2 threshold=0.05 per year
for r in records:
    if r.get('name') == 'X2_threshold_0.05':
        print(f"\n=== {r['name']} ({r['ts']}) ===")
        print(f"{'year':>5}  {'n_conf':>7}  {'fpt_edge':>9}  {'fpt_acc':>8}")
        for yr in r['per_year']:
            edge = yr.get('fpt_edge')
            if edge is not None:
                print(f"  {yr['year']:>5}  {yr.get('n_total','?'):>7}  {edge*100:>+8.2f}%  {yr.get('fpt_acc',0)*100:>7.1f}%")
