# FIELDWISE

**Know your land. Grow your future.**

*A crop-rotation decision-support prototype developed for the NASA Space Apps Challenge 2026 — “Field Shift: Adapting Farms with NASA Data”.*

[**Explore the online demo**](https://gasiamola.vercel.app/) · [**Watch the presentation**](https://gasiamola.vercel.app/presentation) · [**Explore the project**](https://gasiamola.vercel.app/progetto) · [**Read the technical report (PDF)**](frontend/public/project/fieldwise-technical-report.pdf)

> **Project status: research prototype.** The web demo works, but initial data retrieval and computation may be slow on hosted infrastructure. Run the application locally for a more practical hands-on experience. Results are model estimates, **not agronomic prescriptions**.

## Who we are

We are **Vittorio Tesch, Matteo De Martini, Alessandro Pozzolini Gobbi, Marco Cortese, Lorenzo Valente and Mattia D’Agostino**. We developed FIELDWISE during the **NASA Space Apps Challenge, 14–15 November 2026, at Politecnico di Milano**, in response to the challenge *Field Shift: Adapting Farms with NASA Data*.

Our starting question was simple: **how can we turn Earth-observation data into information that genuinely helps farmers decide what to grow next?** We brought together environmental datasets, crop and soil modelling, economic reasoning and web development to create an accessible way to explore that decision.

FIELDWISE is an independent hackathon project. It is not an official NASA product or an agricultural advisory certification.

## Why we built FIELDWISE

A farmer chooses crops before knowing the weather they will face. That choice affects much more than the next harvest: it influences water demand, fertilizer requirements, soil conditions, costs and the crops that can follow.

Meanwhile, increasing climate uncertainty, water scarcity and soil degradation make those trade-offs harder to evaluate. Valuable environmental data already exist, but transforming them into a comparison of realistic farming options requires time and specialist knowledge.

**FIELDWISE makes the trade-offs visible.** Rather than declaring a universally “best” crop rotation, it lets users compare alternatives under shared assumptions and select the priorities that matter to their farm. The final decision remains with farmers and agronomists.

## What the platform does

| Capability | What it offers |
| --- | --- |
| **Map-based field selection** | Select an agricultural area and prepare weather and soil inputs for the chosen location. |
| **Crop-rotation comparisons** | Explore maize, soybean and soft-wheat sequences, with optional rye cover crops. The initial search includes **216 crop/cover combinations**, reduced to **45 distinct classes per irrigation scenario** in the Cremona study. |
| **Resource and soil accounting** | Simulate crop development, water use, nitrogen requirements, nitrogen leaching and humus changes across successive crops. |
| **Farmer-defined priorities** | Compare yield, historical downside performance, irrigation, fertilizer, soil indicators and a modelled economic margin using configurable weights. |
| **Management and compliance scenarios** | Compare rainfed, capped-irrigation and unrestricted-irrigation assumptions, with encoded regional compliance checks. |
| **Climate exploration** | Explore experimental CMIP6 delta-change stress tests across different horizons and emissions scenarios. These are conditional scenarios, **not forecasts**. |
| **Longer-term optimization** | Experiment with a three-cycle (nominally nine-year) Beam Search, preserving simulated soil state between crop cycles. |
| **Explainable outputs** | Review comparisons, warnings and reports instead of receiving an unexplained recommendation. |

The **[Presentation page](https://gasiamola.vercel.app/presentation)** includes a [product introduction](https://youtu.be/UV4a4Smva1A) and a [feature walkthrough](https://youtu.be/bAd1ZywMT-Y).

## How it works

```text
Field and management choices
            |
            v
NASA POWER weather + SoilGrids soil properties
            |
            v
Daily crop, water, nitrogen and humus simulation
            |
            v
Historical scenarios + economic and regulatory checks
            |
            v
Weighted comparison, uncertainty notes and reports
```

The main engine uses daily physical and agronomic relationships, including FAO-based evapotranspiration and yield-response methods. Soil water, mineral nitrogen, residues and humus carry over from one crop to the next. Historical weather provides **comparative scenarios**, not a prediction of the next growing season.

### Data and scientific evidence

- **Core inputs:** NASA POWER meteorological data and SoilGrids soil-property estimates, supplemented by documented agronomic parameters and regional reference values.
- **Quality-checked historical reference:** **2000–2022** at the Cremona pilot, with **17 successful historical starting years** after the warm-up procedure. More recent rainfall data were excluded from this reference because of local quality checks.
- **Evaluation sources:** SMAP soil moisture, MODIS NDVI, ECOSTRESS evapotranspiration, ARPA Lombardia observations and ISTAT provincial crop yields, with GPM IMERG used in precipitation comparisons.

At the **Cremona pilot**, the study found a correlation of approximately **0.70** between simulated and SMAP surface-moisture anomalies, **0.60** between simulated maize water stress and MODIS NDVI, and **0.70** between simulated and detrended provincial maize yields under capped irrigation. These results support **selected model behaviours**, not every output. Soybean yield results were inconclusive, wheat yield correlation was negative, and the exact ranking of alternatives was sensitive to uncertain parameters.

**Important limits:** validation is concentrated on the Cremona pilot; humus and nitrogen processes have not been independently validated at field scale; the economic output is a **partial margin**, not total farm profit; and applying the model elsewhere requires appropriate local inputs and further validation. See the [technical report](frontend/public/project/fieldwise-technical-report.pdf) and [Project section](https://gasiamola.vercel.app/progetto) for methods, evidence and limitations.

## Try FIELDWISE

### Online demo

Open **[gasiamola.vercel.app](https://gasiamola.vercel.app/)** to explore the interface. The hosted version is a showcase of a working prototype, **not yet an optimized production service**: preparing NASA POWER and SoilGrids data for a new field can be slow, and some operations depend on the backend being available. The presentation videos offer a faster overview of the intended experience.

### Run locally

**Requirements:** Python **3.11+**, Node.js compatible with **Next.js 16**, npm, and Git. An internet connection is needed to acquire uncached environmental data.

1. **Clone the repository:**

   ```bash
   git clone https://github.com/AlessandroPozzoliniGobbi/Gasiamola.git
   cd Gasiamola
   ```

2. **Prepare the Python backend** (PowerShell on Windows):

   ```powershell
   py -3.12 -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements-api.txt
   .\.venv\Scripts\python.exe -m pip install -e .
   .\.venv\Scripts\python.exe -m uvicorn api:app --reload --host 127.0.0.1 --port 8000
   ```

   On macOS/Linux, use `python3 -m venv .venv`, `.venv/bin/python -m pip ...` and `.venv/bin/python -m uvicorn ...` instead. Leave the backend terminal running. The API documentation is at **http://127.0.0.1:8000/docs**.

3. **Prepare the frontend** in a **second terminal**:

   ```bash
   cd frontend
   npm ci
   ```

   Create `frontend/.env.local` (you can copy `frontend/.env.example`) and configure:

   ```dotenv
   NEXT_PUBLIC_FIELDWISE_API_URL=http://127.0.0.1:8000
   NEXT_PUBLIC_MAPTILER_KEY=
   ```

   The **MapTiler key is optional** for the core analysis but required for the satellite map layer. Obtain your own key and configure permitted website origins if needed. Do **not** commit `.env.local` or private credentials. Variables prefixed `NEXT_PUBLIC_` are exposed to the browser.

4. **Start the frontend** from `frontend/`:

   ```bash
   npm run dev
   ```

   Open **http://localhost:3000**. Keep both terminals running.

**A note on first-time setup:** a fresh clone may not include the local weather/soil caches generated during our tests. Preparing a new location can therefore take time and requires network access. Once prepared, compatible cached inputs can be reused. Set `FIELDWISE_OFFLINE=1` **only when the required caches already exist**.

### Tests

From the repository root, with Python dependencies installed:

```bash
python -m pytest -m "not slow and not network"
```

## Repository structure

```text
frontend/                  Next.js website, interactive map, reports and presentation
api.py                     FastAPI endpoints
src/fieldwise/             Crop, water, soil, nitrogen, economics and ranking engine
local_analysis.py          Location-specific data preparation and analysis
future_alternatives.py     Experimental climate-scenario comparisons
beam_jobs.py               Background management of longer optimization jobs
params/                    Model parameters and documented assumptions
data/                      Input datasets and generated local caches
reports/                   Model validation, sensitivity and supporting analyses
docs/                      Technical notes and backend reference
tests/                     Automated tests
```

For the more detailed Python API, model outputs, cache formats and cautions from the original developer README, see **[Backend technical reference](docs/ENGINE_REFERENCE.md)**. For longer-term optimization, see **[Beam Search integration notes](docs/INTEGRAZIONE_BEAM_SEARCH.md)**.

## Project report and acknowledgements

The complete report covers the decision problem, data provenance, model equations, validation results, economic and stakeholder analysis, limitations and future development:

**[Download the FIELDWISE Technical Report (PDF)](frontend/public/project/fieldwise-technical-report.pdf)**

This project builds on NASA POWER and other datasets and methods from their respective providers, including ISRIC SoilGrids, NASA SMAP, MODIS, ECOSTRESS, GPM IMERG, ARPA Lombardia, ERSAF and ISTAT. We thank the scientific and open-data communities whose work makes this kind of exploration possible. Data providers do not endorse FIELDWISE or its recommendations.

## Contributing and reuse

Issues and suggestions are welcome, especially around independent field validation, soil processes, new crop parameters, uncertainty reporting and faster data preparation. Please open an issue before proposing major model changes, and keep parameter assumptions and data provenance documented.

**License:** this repository does not currently include a software license. Publication on GitHub should not be interpreted as a grant of permission to reuse or redistribute the code. The team should select and add an explicit `LICENSE` file if it intends to allow reuse.

---

*FIELDWISE — NASA Space Apps Challenge 2026 · Field Shift: Adapting Farms with NASA Data*
