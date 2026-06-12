# 🗺️ Luigi Vault Map

Live mind map of Luigi's Founder Pain Mining System.

- **Live data:** Pulled from `/Users/openclaw/.hermes/leads-vault/` on every regeneration
- **Stack:** Static HTML + D3.js force graph + Python data generator
- **Deploys to:** https://fooxluigi-dev.github.io/luigivaultmap/

## Files

- `index.html` — Main page (D3 force graph, stats bar, scan pipeline, live ticker)
- `vault-data.json` — Generated data the page reads
- `build_vault_map.py` — Python script that scans the vault and writes `vault-data.json`

## Regenerating the data

```bash
python3 build_vault_map.py
```

This reads the leads-vault directory and produces `vault-data.json` with:
- File counts per folder
- Canonical pain mention counts and Luigi Edge Scores
- Recent inbox files with timestamps
- Last 4 cron run timestamps
- Force-graph nodes/edges (folders + pain files + recent inbox)

## Auto-refresh

Currently the HTML auto-reloads every 5 minutes to pick up new data. The build script can be wired to the pain-mining cron so the data regenerates after every scan (planned for v2).

## Privacy

All data is public (this is a GitHub Pages site). No personal info, just counts and metadata. The site is a dashboard for Luigi's own use, kept public for transparency.
