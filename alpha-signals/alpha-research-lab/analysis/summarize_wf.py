import json

with open('wf_results.jsonl') as f:
    records = [json.loads(l) for l in f if l.strip()]

target = {
    'E8_rel_plus_tech','E19_rel_dir_10d','E20_rel_dir_20d','E21_tet_calendar',
    'E22_vol_regime','E23_risk_adj_momentum','E24_earnings_cycle',
    'E27_seasonality','E28_calendar_full','E25_market_breadth',
    'E29_fundamentals','E30_global_risk'
}

# dedupe: keep last run per name
seen = {}
for r in records:
    if r['name'] in target:
        seen[r['name']] = r

print(f"\n  {'name':<30} {'avg_edge':>9}  {'std':>6}  {'sig':>5}  2019    2020    2021    2022    2023    2024    2025")
print('  ' + '-'*110)

order = ['E8_rel_plus_tech','E19_rel_dir_10d','E20_rel_dir_20d','E21_tet_calendar',
         'E22_vol_regime','E23_risk_adj_momentum','E24_earnings_cycle',
         'E27_seasonality','E28_calendar_full','E25_market_breadth',
         'E29_fundamentals','E30_global_risk']

for name in order:
    if name not in seen:
        continue
    r = seen[name]
    py = {yr['year']: yr['edge'] for yr in r['per_year']}
    def e(y):
        if y not in py: return '  N/A '
        v = py[y]*100
        return f'{v:+.1f}%'
    print(f"  {r['name']:<30} {r['avg_edge']*100:>+8.2f}%  {r['std_edge']*100:>5.2f}%  {r['n_sig_years']:>2}/{r['total_years']}  {e(2019):>7} {e(2020):>7} {e(2021):>7} {e(2022):>7} {e(2023):>7} {e(2024):>7} {e(2025):>7}")
