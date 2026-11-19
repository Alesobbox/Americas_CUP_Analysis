"""Versioned public environmental data-source registry and venue routing policy."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

REGISTRY_VERSION = "env-registry-1"

MAX_CONCURRENT_REQUESTS = 2
REQUEST_TIMEOUT_SECONDS = 30.0
MAX_RETRIES = 3
SPLIT_THRESHOLD_BYTES = 32 * 1024 * 1024  # 32 MiB uncompressed ceiling per subset
BBOX_EXPAND_CELLS = 2

WAVE_PERIOD_DEFINITION = "energy_period_Tm_minus_1_0"
WAVE_DIRECTION_CONVENTION = "from_clockwise_true_north_deg"
CURRENT_DIRECTION_CONVENTION = "towards_clockwise_true_north_deg"


@dataclass(frozen=True)
class ProviderSpec:
    """Immutable specification of one public dataset/variable-group provider."""

    provider_id: str
    adapter: str
    group: str
    provider_name: str
    dataset_id: str
    dataset_version: str
    variables: tuple[str, ...]
    units: dict[str, str]
    temporal_support: str
    native_step_s: int
    approx_spacing_deg: float
    depth_m: float | None
    temperature_convention: str | None
    product_classification: str
    endpoint: str
    attribution_url: str
    wave_period_definition: str | None = None
    wave_direction_convention: str | None = None
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize provider spec for provenance manifests and verification."""
        return {
            "provider_id": self.provider_id,
            "adapter": self.adapter,
            "group": self.group,
            "provider_name": self.provider_name,
            "dataset_id": self.dataset_id,
            "dataset_version": self.dataset_version,
            "variables": list(self.variables),
            "units": dict(self.units),
            "temporal_support": self.temporal_support,
            "native_step_s": self.native_step_s,
            "approx_spacing_deg": self.approx_spacing_deg,
            "depth_m": self.depth_m,
            "temperature_convention": self.temperature_convention,
            "product_classification": self.product_classification,
            "endpoint": self.endpoint,
            "attribution_url": self.attribution_url,
            "wave_period_definition": self.wave_period_definition,
            "wave_direction_convention": self.wave_direction_convention,
            "notes": self.notes,
        }


PROVIDER_SPECS: dict[str, ProviderSpec] = {
    "copernicus_med_currents": ProviderSpec(
        provider_id="copernicus_med_currents",
        adapter="copernicus",
        group="currents",
        provider_name="Copernicus Marine Mediterranean Physics",
        dataset_id="cmems_mod_med_phy-cur_my_4.2km_PT1H-m",
        dataset_version="202511",
        variables=("uo", "vo"),
        units={"uo": "m/s", "vo": "m/s"},
        temporal_support="hourly_mean",
        native_step_s=3600,
        approx_spacing_deg=1.0 / 24.0,
        depth_m=1.0182366,
        temperature_convention=None,
        product_classification="retrospective_reanalysis",
        endpoint="copernicusmarine://cmems_mod_med_phy-cur_my_4.2km_PT1H-m",
        attribution_url="https://data.marine.copernicus.eu/product/MEDSEA_MULTIYEAR_PHY_006_004/description",
        notes="Hourly mean geographic east/north surface velocity at shallowest valid layer (~1.018 m).",
    ),
    "copernicus_med_water_temp": ProviderSpec(
        provider_id="copernicus_med_water_temp",
        adapter="copernicus",
        group="water_temperature",
        provider_name="Copernicus Marine Mediterranean Physics",
        dataset_id="cmems_mod_med_phy-temp_my_4.2km_P1D-m",
        dataset_version="202511",
        variables=("thetao",),
        units={"thetao": "degC"},
        temporal_support="daily_mean",
        native_step_s=86400,
        approx_spacing_deg=1.0 / 24.0,
        depth_m=1.0182366,
        temperature_convention="potential",
        product_classification="retrospective_reanalysis",
        endpoint="copernicusmarine://cmems_mod_med_phy-temp_my_4.2km_P1D-m",
        attribution_url="https://data.marine.copernicus.eu/product/MEDSEA_MULTIYEAR_PHY_006_004/description",
        notes="Daily mean potential temperature at shallowest valid layer (~1.018 m).",
    ),
    "copernicus_med_waves": ProviderSpec(
        provider_id="copernicus_med_waves",
        adapter="copernicus",
        group="waves",
        provider_name="Copernicus Marine Mediterranean Waves",
        dataset_id="cmems_mod_med_wav_my_4.2km_PT1H-i",
        dataset_version="202511",
        variables=("VHM0", "VTM10", "VMDR"),
        units={"VHM0": "m", "VTM10": "s", "VMDR": "deg"},
        temporal_support="hourly_instantaneous",
        native_step_s=3600,
        approx_spacing_deg=1.0 / 24.0,
        depth_m=None,
        temperature_convention=None,
        product_classification="retrospective_reanalysis",
        endpoint="copernicusmarine://cmems_mod_med_wav_my_4.2km_PT1H-i",
        attribution_url="https://data.marine.copernicus.eu/product/MEDSEA_MULTIYEAR_WAV_006_012/description",
        wave_period_definition=WAVE_PERIOD_DEFINITION,
        wave_direction_convention=WAVE_DIRECTION_CONVENTION,
        notes="Hourly instantaneous waves; VTM10 is energy period Tm-1,0 and VMDR is wave-from bearing.",
    ),
    "parthenope_naples_ww3": ProviderSpec(
        provider_id="parthenope_naples_ww3",
        adapter="parthenope",
        group="waves",
        provider_name="UniParthenope CCMMMA WW3 (Naples d03)",
        dataset_id="ww33_d03",
        dataset_version="d03-archive",
        variables=("hs", "period", "dir"),
        units={"hs": "m", "period": "s", "dir": "deg"},
        temporal_support="hourly_instantaneous",
        native_step_s=3600,
        approx_spacing_deg=0.003,
        depth_m=None,
        temperature_convention=None,
        product_classification="archived_forecast",
        endpoint="https://data.meteo.uniparthenope.it/opendap/ww33/d03/archive/{YYYY}/{MM}/{DD}/ww33_d03_{YYYY}{MM}{DD}Z{HH}00.nc",
        attribution_url="https://meteo.uniparthenope.it/open-data/",
        wave_period_definition=WAVE_PERIOD_DEFINITION,
        wave_direction_convention=WAVE_DIRECTION_CONVENTION,
        notes="WW3 d03 archive; period maps native t0m1 and dir is wave-from bearing.",
    ),
    "parthenope_naples_wrf": ProviderSpec(
        provider_id="parthenope_naples_wrf",
        adapter="parthenope",
        group="air_temperature",
        provider_name="UniParthenope CCMMMA WRF (Naples d03)",
        dataset_id="wrf5_d03",
        dataset_version="d03-archive",
        variables=("T2C",),
        units={"T2C": "degC"},
        temporal_support="hourly_instantaneous",
        native_step_s=3600,
        approx_spacing_deg=0.008,
        depth_m=2.0,
        temperature_convention=None,
        product_classification="archived_forecast",
        endpoint="https://data.meteo.uniparthenope.it/opendap/wrf5/d03/archive/{YYYY}/{MM}/{DD}/wrf5_d03_{YYYY}{MM}{DD}Z{HH}00.nc",
        attribution_url="https://meteo.uniparthenope.it/open-data/",
        notes="2 m air temperature in Celsius from Parthenope WRF d03 OPeNDAP archive.",
    ),
    "parthenope_naples_rms3_temp": ProviderSpec(
        provider_id="parthenope_naples_rms3_temp",
        adapter="parthenope",
        group="water_temperature",
        provider_name="UniParthenope CCMMMA ROMS (Naples d03)",
        dataset_id="rms3_d03",
        dataset_version="d03-archive",
        variables=("tempSurface",),
        units={"tempSurface": "degC"},
        temporal_support="hourly_instantaneous",
        native_step_s=3600,
        approx_spacing_deg=0.002,
        depth_m=None,
        temperature_convention="potential",
        product_classification="archived_forecast",
        endpoint="https://data.meteo.uniparthenope.it/opendap/rms3/d03/archive/{YYYY}/{MM}/{DD}/rms3_d03_{YYYY}{MM}{DD}Z{HH}00.nc",
        attribution_url="https://meteo.uniparthenope.it/open-data/",
        notes="ROMS processed tempSurface potential temperature; actual first depth (~3.166 m) read from depth coordinate.",
    ),
    "open_meteo_arome_france_hd": ProviderSpec(
        provider_id="open_meteo_arome_france_hd",
        adapter="open_meteo",
        group="air_temperature",
        provider_name="MeteoFrance AROME HD via Open-Meteo",
        dataset_id="meteofrance_arome_france_hd",
        dataset_version="historical-forecast-api",
        variables=("temperature_2m",),
        units={"temperature_2m": "degC"},
        temporal_support="hourly_instantaneous",
        native_step_s=3600,
        approx_spacing_deg=0.025,
        depth_m=2.0,
        temperature_convention=None,
        product_classification="archived_forecast",
        endpoint="https://historical-forecast-api.open-meteo.com/v1/forecast",
        attribution_url="https://open-meteo.com/en/docs/historical-forecast-api",
        notes="Explicit AROME France HD model selection with cell_selection=sea and UTC timestamps.",
    ),
    "open_meteo_icon_2i": ProviderSpec(
        provider_id="open_meteo_icon_2i",
        adapter="open_meteo",
        group="air_temperature",
        provider_name="ARPAE ICON-2I via Open-Meteo",
        dataset_id="italia_meteo_arpae_icon_2i",
        dataset_version="historical-forecast-api",
        variables=("temperature_2m",),
        units={"temperature_2m": "degC"},
        temporal_support="hourly_instantaneous",
        native_step_s=3600,
        approx_spacing_deg=0.02,
        depth_m=2.0,
        temperature_convention=None,
        product_classification="archived_forecast",
        endpoint="https://historical-forecast-api.open-meteo.com/v1/forecast",
        attribution_url="https://open-meteo.com/en/docs/historical-forecast-api",
        notes="Explicit ICON-2I model selection with cell_selection=sea and UTC timestamps.",
    ),
    "open_meteo_ecmwf_ifs": ProviderSpec(
        provider_id="open_meteo_ecmwf_ifs",
        adapter="open_meteo",
        group="air_temperature",
        provider_name="ECMWF IFS via Open-Meteo",
        dataset_id="ecmwf_ifs",
        dataset_version="historical-forecast-api",
        variables=("temperature_2m",),
        units={"temperature_2m": "degC"},
        temporal_support="hourly_instantaneous",
        native_step_s=3600,
        approx_spacing_deg=0.09,
        depth_m=2.0,
        temperature_convention=None,
        product_classification="archived_forecast",
        endpoint="https://historical-forecast-api.open-meteo.com/v1/forecast",
        attribution_url="https://open-meteo.com/en/docs/historical-forecast-api",
        notes="Explicit ECMWF IFS model selection with cell_selection=sea and UTC timestamps.",
    ),
    "hycom_gofs31_currents": ProviderSpec(
        provider_id="hycom_gofs31_currents",
        adapter="hycom",
        group="currents",
        provider_name="HYCOM GOFS 3.1 Reanalysis/Analysis",
        dataset_id="GLBy0.08/expt_93.0/uv3z/2023",
        dataset_version="expt_93.0",
        variables=("water_u", "water_v"),
        units={"water_u": "m/s", "water_v": "m/s"},
        temporal_support="3hourly_instantaneous",
        native_step_s=10800,
        approx_spacing_deg=0.08,
        depth_m=0.0,
        temperature_convention=None,
        product_classification="retrospective_reanalysis",
        endpoint="https://tds.hycom.org/thredds/ncss/GLBy0.08/expt_93.0/uv3z/2023",
        attribution_url="https://www.hycom.org/dataserver/gofs-3pt1/analysis",
        notes="Surface 0 m velocity only; hourly depth-averaged velocities rejected.",
    ),
    "hycom_gofs31_water_temp": ProviderSpec(
        provider_id="hycom_gofs31_water_temp",
        adapter="hycom",
        group="water_temperature",
        provider_name="HYCOM GOFS 3.1 Reanalysis/Analysis",
        dataset_id="GLBy0.08/expt_93.0/ts3z/2023",
        dataset_version="expt_93.0",
        variables=("water_temp",),
        units={"water_temp": "degC"},
        temporal_support="3hourly_instantaneous",
        native_step_s=10800,
        approx_spacing_deg=0.08,
        depth_m=0.0,
        temperature_convention="in_situ",
        product_classification="retrospective_reanalysis",
        endpoint="https://tds.hycom.org/thredds/ncss/GLBy0.08/expt_93.0/ts3z/2023",
        attribution_url="https://www.hycom.org/dataserver/gofs-3pt1/analysis",
        notes="In-situ surface temperature at 0 m.",
    ),
    "copernicus_glorys12_currents": ProviderSpec(
        provider_id="copernicus_glorys12_currents",
        adapter="copernicus",
        group="currents",
        provider_name="Copernicus Marine GLORYS12",
        dataset_id="cmems_mod_glo_phy_my_0.083deg_P1D-m",
        dataset_version="202311",
        variables=("uo", "vo"),
        units={"uo": "m/s", "vo": "m/s"},
        temporal_support="daily_mean",
        native_step_s=86400,
        approx_spacing_deg=1.0 / 12.0,
        depth_m=0.494025,
        temperature_convention=None,
        product_classification="retrospective_reanalysis",
        endpoint="copernicusmarine://cmems_mod_glo_phy_my_0.083deg_P1D-m",
        attribution_url="https://data.marine.copernicus.eu/product/GLOBAL_MULTIYEAR_PHY_001_030/description",
        notes="Jeddah currents fallback: daily mean surface vectors at ~0.494 m.",
    ),
    "copernicus_glorys12_water_temp": ProviderSpec(
        provider_id="copernicus_glorys12_water_temp",
        adapter="copernicus",
        group="water_temperature",
        provider_name="Copernicus Marine GLORYS12",
        dataset_id="cmems_mod_glo_phy_my_0.083deg_P1D-m",
        dataset_version="202311",
        variables=("thetao",),
        units={"thetao": "degC"},
        temporal_support="daily_mean",
        native_step_s=86400,
        approx_spacing_deg=1.0 / 12.0,
        depth_m=0.494025,
        temperature_convention="potential",
        product_classification="retrospective_reanalysis",
        endpoint="copernicusmarine://cmems_mod_glo_phy_my_0.083deg_P1D-m",
        attribution_url="https://data.marine.copernicus.eu/product/GLOBAL_MULTIYEAR_PHY_001_030/description",
        notes="Jeddah water temperature fallback: daily mean potential temperature at ~0.494 m.",
    ),
    "copernicus_waverys_waves": ProviderSpec(
        provider_id="copernicus_waverys_waves",
        adapter="copernicus",
        group="waves",
        provider_name="Copernicus Marine WAVERYS",
        dataset_id="cmems_mod_glo_wav_my_0.2deg_PT3H-i",
        dataset_version="202411",
        variables=("VHM0", "VTM10", "VMDR"),
        units={"VHM0": "m", "VTM10": "s", "VMDR": "deg"},
        temporal_support="3hourly_instantaneous",
        native_step_s=10800,
        approx_spacing_deg=0.2,
        depth_m=None,
        temperature_convention=None,
        product_classification="retrospective_reanalysis",
        endpoint="copernicusmarine://cmems_mod_glo_wav_my_0.2deg_PT3H-i",
        attribution_url="https://data.marine.copernicus.eu/product/GLOBAL_MULTIYEAR_WAV_001_032/description",
        wave_period_definition=WAVE_PERIOD_DEFINITION,
        wave_direction_convention=WAVE_DIRECTION_CONVENTION,
        notes="3-hourly instantaneous waves (~0.2 deg); VTM10 is Tm-1,0.",
    ),
}

REJECTED_SOURCES: dict[str, dict[str, Any]] = {
    "parthenope_rms3_currents": {
        "provider": "UniParthenope CCMMMA ROMS d03",
        "variables": ["u", "v", "cur"],
        "status": "rejected_for_production",
        "reason": (
            "Processed ROMS surface currents exhibit unresolved vector orientation "
            "and an undocumented 1.2 scaling multiplier in ccmmma-postpro; rejected "
            "in favor of Copernicus Mediterranean hourly currents."
        ),
        "reference": "https://github.com/CCMMMA/ccmmma-postpro",
    },
    "open_meteo_best_match": {
        "provider": "Open-Meteo automatic best_match",
        "status": "prohibited",
        "reason": "Implicit model mixing disallowed in environment-2; explicit model IDs required.",
    },
    "hycom_depth_averaged_velocity": {
        "provider": "HYCOM GOFS 3.1 barotropic/depth-averaged",
        "status": "prohibited",
        "reason": "Hourly depth-averaged velocities must never substitute for surface currents.",
    },
}


@dataclass(frozen=True)
class VenuePolicy:
    """Venue coordinate window and ordered variable-group provider chains."""

    venue_id: str
    display_name: str
    lat_bounds: tuple[float, float]
    lon_bounds: tuple[float, float]
    period_label: str
    providers: dict[str, tuple[str, ...]]


VENUE_POLICIES: dict[str, VenuePolicy] = {
    "vilanova": VenuePolicy(
        venue_id="vilanova",
        display_name="Vilanova i la Geltru",
        lat_bounds=(40.8, 41.5),
        lon_bounds=(1.2, 2.0),
        period_label="2023-09",
        providers={
            "currents": ("copernicus_med_currents",),
            "waves": ("copernicus_med_waves",),
            "air_temperature": ("open_meteo_arome_france_hd",),
            "water_temperature": ("copernicus_med_water_temp",),
        },
    ),
    "jeddah": VenuePolicy(
        venue_id="jeddah",
        display_name="Jeddah",
        lat_bounds=(21.0, 22.3),
        lon_bounds=(38.5, 39.6),
        period_label="2023-11..2023-12",
        providers={
            "currents": ("hycom_gofs31_currents", "copernicus_glorys12_currents"),
            "waves": ("copernicus_waverys_waves",),
            "air_temperature": ("open_meteo_ecmwf_ifs",),
            "water_temperature": ("hycom_gofs31_water_temp", "copernicus_glorys12_water_temp"),
        },
    ),
    "barcelona": VenuePolicy(
        venue_id="barcelona",
        display_name="Barcelona",
        lat_bounds=(41.1, 41.7),
        lon_bounds=(2.0, 2.6),
        period_label="2024-08..2024-10",
        providers={
            "currents": ("copernicus_med_currents",),
            "waves": ("copernicus_med_waves",),
            "air_temperature": ("open_meteo_arome_france_hd",),
            "water_temperature": ("copernicus_med_water_temp",),
        },
    ),
    "cagliari": VenuePolicy(
        venue_id="cagliari",
        display_name="Cagliari",
        lat_bounds=(38.8, 39.5),
        lon_bounds=(8.8, 9.6),
        period_label="2026-05",
        providers={
            "currents": ("copernicus_med_currents",),
            "waves": ("copernicus_med_waves",),
            "air_temperature": ("open_meteo_icon_2i",),
            "water_temperature": ("copernicus_med_water_temp",),
        },
    ),
    "naples": VenuePolicy(
        venue_id="naples",
        display_name="Naples",
        lat_bounds=(40.4, 41.1),
        lon_bounds=(13.8, 14.7),
        period_label="2026-09",
        providers={
            "currents": ("copernicus_med_currents",),
            "waves": ("parthenope_naples_ww3", "copernicus_med_waves"),
            "air_temperature": ("parthenope_naples_wrf", "open_meteo_icon_2i"),
            "water_temperature": ("parthenope_naples_rms3_temp", "copernicus_med_water_temp"),
        },
    ),
}


def resolve_venue_policy(latitude: float | None, longitude: float | None) -> VenuePolicy | None:
    """Resolve venue policy strictly from numeric WGS-84 coordinates."""
    if latitude is None or longitude is None:
        return None
    for policy in VENUE_POLICIES.values():
        lat_min, lat_max = policy.lat_bounds
        lon_min, lon_max = policy.lon_bounds
        if lat_min <= latitude <= lat_max and lon_min <= longitude <= lon_max:
            return policy
    return None


def build_provider_audit() -> dict[str, Any]:
    """Return versioned provider policy and documented rejections."""
    return {
        "registry_version": REGISTRY_VERSION,
        "conventions": {
            "wave_period": WAVE_PERIOD_DEFINITION,
            "wave_direction": WAVE_DIRECTION_CONVENTION,
            "current_direction": CURRENT_DIRECTION_CONVENTION,
        },
        "venues": {
            vid: {
                "display_name": p.display_name,
                "period_label": p.period_label,
                "lat_bounds": list(p.lat_bounds),
                "lon_bounds": list(p.lon_bounds),
                "providers": {k: list(v) for k, v in p.providers.items()},
            }
            for vid, p in VENUE_POLICIES.items()
        },
        "providers": {pid: spec.to_dict() for pid, spec in PROVIDER_SPECS.items()},
        "rejected_sources": REJECTED_SOURCES,
    }
