# Run Summaries

Main experiment runners write compact machine-readable summaries here.

Files are expected to include:

- one permanent timestamped JSON per run
- one convenience pointer named `latest_<mode>.json`

Current modes:

- `one_shot`
- `walk_forward`
- `cross_sectional`
- `ensemble`
- `portfolio`

Read these files before inspecting larger logs when you only need the minimal result.
