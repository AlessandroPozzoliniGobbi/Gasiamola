# FIELDWISE — 9-year Beam Search integration

This patch is based on `Gasiamola-integrazione.zip`, the code provided on 15 November 2026. Apply it **only in the `Gasiamola-integrazione` worktree**, not in the original showcase folder.

## What's new

- `POST /api/v1/beam-search`: validates an explicit field location, the three objectives (yield, margin, cost), irrigation, regulations, climate forcing and optional farmer costs; returns a background job ID.
- `GET /api/v1/beam-search/{job_id}`: returns `running`, `ready` with the JSON report, or `failed` with an error. Jobs are bounded and remain in memory; a server restart loses them.
- `frontend/src/components/analysis/BeamOptimizerPanel.tsx`: optional panel on the existing field-analysis page with three objective selectors, historical/CMIP6 modes, progress, results for all three cycles, soil inheritance, crop details, warnings, and JSON export.
- `src/fieldwise/beam_optimizer.py`: preserves the ancestry of the selected beam trajectory. The displayed cycles now share *one actual branch* with soil state carried between stages, instead of potentially mixing winning cycles from unrelated branches. A strict regional-compliance selection does **not** fall back to derogations. Economic assumptions are passed through the engine parameter tree so custom crop costs affect the optimization.
- `local_analysis.py`: excludes this optional optimizer from the **historical ensemble** engine-source fingerprint, to avoid invalidating existing historical caches for presentation-only/output changes. Other scientific model files remain fingerprinted.

## Explicit limitations

- Three successive rotations of three crops are optimized, **not necessarily exactly nine calendar years**. Cropping dates and growth periods control the actual duration.
- The selected first rotation is not treated as an initial state in the 9-year optimizer. The optimizer chooses new sequences given the chosen climate, regulation and objective for each stage. This is a separate exploratory comparison; the existing 3-year baseline report is unchanged.
- For a field outside the pilot's cache cell, the backend requires a valid local NASA POWER + SoilGrids preparation. The API **never silently substitutes** the pilot soil or weather. The UI can explicitly request the Cremona pilot reference instead, labelled as such in the output.
- Historical and climate simulations remain experiments, not validated field forecasts or a legal certification. Regulatory checks implement only the engine's encoded rules. Derogation-only or unassessable options are not recommended.
- `best_sim_*` values are standalone benchmarks at the stage's reference soil state, not guaranteed to describe the soil state on the finally selected path. The headline results do describe one consistent path.
- The advertised brute-force runtime in the engine contract is a **hypothetical estimate**, not a measured comparator.
- A single-worker, in-memory job manager is suitable for a small demo, **not production**: restarts interrupt work; multiple workers don't share jobs; there is no authentication or persistent queue. Put API authentication, per-user rate limits and a durable queue in place before exposing it widely.
- The existing 3-year analysis and Future Projections report/exports are untouched. Nine-year results are shown in the separate panel and can be exported as JSON, not yet as part of the old report PDF.

## Apply the ZIP in PowerShell (worktree ONLY)

```powershell
cd C:\Users\Aless\Documents\GitHub\Gasiamola-integrazione

git status
# Download FIELDWISE-beam-search-integration.zip to this folder.
Expand-Archive -LiteralPath .\FIELDWISE-beam-search-integration.zip -DestinationPath . -Force

git diff --stat
```

Or apply the alternate patch:

```powershell
git apply --check --ignore-space-change .\FIELDWISE-beam-search.patch
git apply --ignore-space-change .\FIELDWISE-beam-search.patch
```

**Do not apply both the ZIP and patch.** They make the same changes. The code is not automatically pushed to GitHub.

## Test

Start the Python API from the repository root in the existing `.venv`:

```powershell
$env:FIELDWISE_OFFLINE='1'
python -m pytest tests/test_beam_http_integration.py tests/test_beam_optimizer.py tests/test_api_integration.py -q
python -m uvicorn api:app --reload --host 127.0.0.1 --port 8000
```

In a second terminal:

```powershell
cd frontend
npm ci
npm run build
npm run dev
```

Open the existing saved field on `/analizza/<field-id>`, scroll to **9-year crop rotation optimizer**, select an objective for each cycle, and run it. A field other than the Cremona pilot must already have current prepared local data. If unavailable, prepare it first through the normal **Run analysis** flow or deliberately opt in to the **Cremona pilot** reference.

If using `.env.local`, verify `NEXT_PUBLIC_FIELDWISE_API_URL=http://127.0.0.1:8000`.

## Push the integration branch only after testing

```powershell
cd C:\Users\Aless\Documents\GitHub\Gasiamola-integrazione
git add api.py beam_jobs.py local_analysis.py src/fieldwise/beam_optimizer.py frontend/src/lib/beamApi.ts frontend/src/components/analysis/BeamOptimizerPanel.tsx frontend/src/styles/beam.module.css frontend/src/views/Analysis.tsx tests/test_beam_http_integration.py tests/test_api_review_fixes.py docs/INTEGRAZIONE_BEAM_SEARCH.md
git commit -m "Integrate nine-year beam optimizer into FIELDWISE analysis"
git push -u origin integrazione/beam-search
```

Open a Pull Request to `main` only when all desired tests and the local showcase flow have been verified. The original `Gasiamola` worktree remains untouched.
