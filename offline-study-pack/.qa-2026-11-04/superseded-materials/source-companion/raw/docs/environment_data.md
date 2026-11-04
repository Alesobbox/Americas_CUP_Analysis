# Historical environment data

The replay header combines recorded race wind with separate hourly Open-Meteo
historical model context: 2 m air temperature, significant wave height and sea
surface temperature. These fields are model grid estimates, not onboard sensor
measurements. The requested point is each replay's actual `course.origin`.
Returned air and marine grid points are retained separately and may differ.

This enrichment is **retrospective replay context only**. It is never imported
by `pipeline/prediction` or used as weather known before a race. Archived forecast
runs for causal probability inputs remain a separate task.

## Acquisition

```text
python -m pipeline.environment
python -m pipeline.environment --race naples_pr1
python -m pipeline.environment --race naples_pr1 --force
python -m pipeline.environment --verify
npm run environment
```

The command reads the catalog and a maximum 1 MiB metadata prefix per replay;
it does not load telemetry arrays or raw source archives. It requests the actual
UTC replay window's dates, including both dates for a midnight crossing. There
is no substitution of today's weather or a nearby date.

- Air: [Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api),
  `https://archive-api.open-meteo.com/v1/archive`, `temperature_2m`.
- Marine: [Marine Weather API](https://open-meteo.com/en/docs/marine-weather-api),
  `https://marine-api.open-meteo.com/v1/marine`, `wave_height` and
  `sea_surface_temperature`, with `cell_selection=sea`.

Requests use UTC Unix timestamps and Celsius. The response must be JSON, at most
2 MiB, and arrive within a 20 second timeout. Units, finite values, nonnegative
wave heights, sorted unique UTC hours, matching array lengths and requested dates
are validated. Null provider samples remain null. A failed air request preserves
valid marine data, and vice versa. Missing dates or hours are not filled by
borrowing another day's values. A failure is written into the corresponding
artifact's `errors` object.

## Export and provenance

`public/data/environment/<race_id>.json` uses `environment-1`. Its `hourly`
object has the sorted union of source `time_ms` values and equally long
`air_temperature_c`, `wave_height_m`, and `water_temperature_c` arrays. Absent
samples are null. `units`, `requested_location`, `replay_window`, and
`context: historical_replay_only` make the interpretation explicit.

Each successful entry under `sources.air` or `sources.marine` records provider,
`product: historical_model`, exact `request_url`, `retrieved_at` in UTC, returned
`grid_location`, exact-response `response_sha256`, and a relative `response_file`.
The raw, unmodified provider bytes are exported at
`public/data/environment/responses/<sha256>.json` for independent checking.

The request lookup cache is `.forecast/environment/<request_url_sha256>.json`.
Reuse verifies its URL, timestamp and the raw response's actual SHA-256. A corrupt
cache fails explicitly; `--force` performs a fresh acquisition. Exported JSON
uses atomic same-directory replacement. Rebuilding one race preserves the rest.
The acquisition command also refreshes the Reports download inventory when the
historical analysis catalog exists, so raw responses remain downloadable.

`--verify` is completely offline. It checks every expected catalog artifact,
metadata, units, source URLs, grid locations, raw response hashes, and exact hourly
values/nulls reconstructed from the original responses. A missing artifact or
tampered response fails verification. Explicit provider failures remain visible
in its compact coverage summary rather than being converted into fake values.

The free service's [attribution and use conditions](https://open-meteo.com/en/terms)
apply. The UI attributes Open-Meteo and labels this context as modeled. Ordinary
unit tests use frozen mock responses and make no live network requests.
