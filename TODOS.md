# TODOS

## Pool Data Integration
**What:** Add `--pool-data picks.csv` CLI argument support.
**Why:** Current pool optimization uses public behavior heuristics (assumes heavy bias toward low seeds). With actual pool picks, the script could compute exact differentiation value per upset pick — knowing which teams are over/underrepresented in your specific pool rather than "the average pool."
**Pros:** More accurate pool optimization, larger edge against field.
**Cons:** Requires user to gather/export their pool's picks each year. Extra data prep step.
**Context:** Chose heuristic approach (Approach A) in 2026 design review. The heuristic works well for generic pools. Layer in actual pool data when the script has been used for a season and the methodology is proven.
**Depends on:** Core simulation engine working correctly first.
**Where to start:** Add `--pool-data` argparse argument, load CSV of `{team_name, pick_pct}`, use pick_pct to replace the hardcoded seed-bias heuristic in `find_upsets()`.
