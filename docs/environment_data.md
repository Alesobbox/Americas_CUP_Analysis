# Historical Environmental Context (`environment-2`)

Each AC38 race replay can be accompanied by historical retrospective environmental context exported under `public/data/environment/` for display in the replay header disclosure (`TacticalHeader.tsx`). Environmental estimates are kept strictly separate from recorded yacht and course wind telemetry and are never interpolated into boat wind channels (`twd` / `tws`).

## Schema (`environment-2`)

- **Course-centre time series (`public/data/environment/<race_id>.json`)**
  - `schema_version`: `"environment-2"`
  - `context`: `"historical_replay_only"`
  - `registry_version`: `"env-registry-1"`
  - `location`: course origin latitude, longitude, and bounding box
  - `window`: replay UTC `start_ms`, `end_ms`, ISO-8601 bounds, and `gun_ms`
  - `channels`: full per-channel provenance (`currents`, `waves`, `air_temperature`, `water_temperature`) including provider, dataset, dataset version, native spatial support, depth/reference height, temperature convention, units, quality status, and subset SHA-256 hashes
  - `course_centre`: hourly UTC arrays for:
    - Surface currents: `current_u_mps`, `current_v_mps`, `current_speed_mps`, `current_dir_towards_deg` (direction nulled below `0.01 m/s` slack threshold)
    - Waves: `wave_height_m`, `wave_period_s`, `wave_dir_from_deg` (period and FROM direction nulled below `0.05 m` calm threshold)
    - Temperatures: `air_temperature_c` (2 m, °C), `water_temperature_c` (shallowest surface level, °C)
- **1 Hz per-boat sampled series (`public/data/environment/boats/<race_id>.json`)**
  - Schema `"environment-boats-1"` containing 1 Hz bilinear/trilinear space-time samples along each boat's WGS84 GNSS track.
- **Provenance bundles (`public/data/environment/bundles/<sha256>.json`)**
  - Content-addressed provider metadata and subset checksums referenced by `bundle_relpath`.

## Provider Registry (`pipeline/env/registry.py`)

| Channel | Naples (Gulf of Naples) Primary | Cagliari (Sardinia) Primary | Secondary / Fallback |
| --- | --- | --- | --- |
| `currents` | Copernicus `cmems_mod_med_phy-cur_anfc_4.2km_PT1H-m` | Copernicus `cmems_mod_med_phy-cur_anfc_4.2km_PT1H-m` | Copernicus GLORYS12 (`cmems_mod_glo_phy_my_0.083deg_P1D-m`) |
| `waves` | Parthenope WW3 (`ww33`) | Copernicus `cmems_mod_med_wav_anfc_4.2km_PT1H-i` | Copernicus WAVERYS / Open-Meteo |
| `air_temperature` | Parthenope WRF (`wrf5`) | Open-Meteo `arome_france_hd` | Open-Meteo `icon_2i` / `ecmwf_ifs` |
| `water_temperature` | Parthenope RMS3 (`rms3`) | Copernicus `cmems_mod_med_phy-tem_anfc_4.2km_PT1H-m` | Copernicus GLORYS12 |

`parthenope_rms3_currents` is explicitly excluded in `REJECTED_SOURCES` because its rotated grid axes lack reliable vector rotation angles in OPeNDAP metadata.

## Pipeline CLI

All cached grid subsets, manifests, inventories, and exported session checks live under `.cache/environment/` (overrideable via `ENV_CACHE_DIR`):

```bash
python -m pipeline.environment inventory   # Reconcile raw Data/AC38/*.jsonl and replay bboxes
python -m pipeline.environment probe       # Probe remote OPeNDAP / Copernicus / Open-Meteo endpoints
python -m pipeline.environment acquire     # Fetch deduplicated NetCDF/JSON subsets into .cache/environment/cache/
python -m pipeline.environment export      # Sample course-centre & 1 Hz boat tracks to public/data/environment/
python -m pipeline.environment verify      # Offline SHA-256 & schema verification across cache and exports
```

Copernicus Marine credentials (`COPERNICUSMARINE_SERVICE_USERNAME`, `COPERNICUSMARINE_SERVICE_PASSWORD`) can be configured via `.env` (see [`.env.example`](../.env.example)); Open-Meteo and Università Parthenope endpoints are unauthenticated.
