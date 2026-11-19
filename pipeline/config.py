"""Configuration and constants for the AC40 2D Regatta Replay pipeline.

Defines geodetic origin, curvature coefficients, course layout,
mark identifiers, competitor catalog, and unit conversion constants.
"""

from dataclasses import dataclass
from typing import Final, Dict, Tuple


LAT0: Final[float] = 40.80948067
LON0: Final[float] = 14.23726898

# WGS84 Ellipsoidal Equirectangular curvature coefficients (metres per degree)
# Evaluated at lat0 = 40.80948067 deg N.
K_LAT: Final[float] = 111047.746
K_LON: Final[float] = 84374.839

# Cagliari origin (~39.18°N, 9.12°E) and local curvature coefficients
CAGLIARI_LAT0: Final[float] = 39.18
CAGLIARI_LON0: Final[float] = 9.12
CAGLIARI_K_LAT: Final[float] = 111019.5
CAGLIARI_K_LON: Final[float] = 86407.9

# Local Gaussian mean radius of curvature at origin sqrt(M * N) in metres
EARTH_RADIUS_LOCAL_M: Final[float] = 6374912.38

# Standard WGS84 authalic mean Earth radius in metres
EARTH_RADIUS_WGS84_M: Final[float] = 6371008.8


COURSE_AXIS_DEG: Final[float] = 39.99999999878744
COURSE_LENGTH_M: Final[float] = 2259.4401327907335

# Sampling & Regularization Grid Configuration
SAMPLE_RATE_HZ: Final[int] = 10
SAMPLE_INTERVAL_MS: Final[int] = 100  # 1000 ms / 10 Hz

# Conversion Factors
# 1 knot = 1852 m / 3600 s => 1 m/s = 3600 / 1852 kt ~= 1.94384449 kt
MPS_TO_KNOTS: Final[float] = 1.94384449
KNOTS_TO_MPS: Final[float] = 1.0 / MPS_TO_KNOTS


MARK_RM1_UUID: Final[str] = "3e0be123-6ef5-4485-8b35-19e84cb4d8dd"
MARK_RM2_UUID: Final[str] = "e018121d-b03e-4be7-9998-2a000135a599"
MARK_RM3_UUID: Final[str] = "d72957d4-4eb3-41ef-9a51-5983a906aa8b"
MARK_RM4_UUID: Final[str] = "a392c0a6-582e-41a6-905e-0e490f3a27b1"
MARK_RM5_UUID: Final[str] = "e0b1111d-3274-475a-a5be-97e1501d58f2"
MARK_RM6_UUID: Final[str] = "c35b7718-40e5-4a9d-a4e6-934d18ecfa2a"
MARK_RM7_UUID: Final[str] = "b001c19e-b70b-484f-947b-4841d7a4842e"
MARK_RM8_UUID: Final[str] = "026f70b1-9ecb-479d-b03c-085e40fd166d"

MARK_UUIDS: Final[Dict[str, str]] = {
    "RM1": MARK_RM1_UUID,
    "RM2": MARK_RM2_UUID,
    "RM3": MARK_RM3_UUID,
    "RM4": MARK_RM4_UUID,
    "RM5": MARK_RM5_UUID,
    "RM6": MARK_RM6_UUID,
    "RM7": MARK_RM7_UUID,
    "RM8": MARK_RM8_UUID,
}

UUID_TO_MARK: Final[Dict[str, str]] = {
    MARK_RM1_UUID: "RM1",
    MARK_RM2_UUID: "RM2",
    MARK_RM3_UUID: "RM3",
    MARK_RM4_UUID: "RM4",
    MARK_RM5_UUID: "RM5",
    MARK_RM6_UUID: "RM6",
    MARK_RM7_UUID: "RM7",
    MARK_RM8_UUID: "RM8",
}

@dataclass(frozen=True)
class MarkInfo:
    code: str
    uuid: str
    name: str
    role: str
    color: str
    target_lat: float
    target_lon: float


MARKS: Final[Dict[str, MarkInfo]] = {
    "RM1": MarkInfo(
        code="RM1",
        uuid=MARK_RM1_UUID,
        name="Race Mark 1",
        role="Gate / Course Mark 1",
        color="#ff2d32",
        target_lat=40.8100,
        target_lon=14.2400,
    ),
    "RM2": MarkInfo(
        code="RM2",
        uuid=MARK_RM2_UUID,
        name="Race Mark 2",
        role="Top Gate Starboard / Windward",
        color="#ff0d13",
        target_lat=40.81669188,
        target_lon=14.24687938,
    ),
    "RM3": MarkInfo(
        code="RM3",
        uuid=MARK_RM3_UUID,
        name="Race Mark 3",
        role="Bottom Gate Port / Start Line Port",
        color="#ff060d",
        target_lat=40.8020,
        target_lon=14.2280,
    ),
    "RM4": MarkInfo(
        code="RM4",
        uuid=MARK_RM4_UUID,
        name="Race Mark 4",
        role="Top Gate Port / Windward",
        color="#ff0f15",
        target_lat=40.81801854,
        target_lon=14.24476155,
    ),
    "RM5": MarkInfo(
        code="RM5",
        uuid=MARK_RM5_UUID,
        name="Race Mark 5",
        role="Gate / Course Mark 5",
        color="#ff373d",
        target_lat=40.8100,
        target_lon=14.2400,
    ),
    "RM6": MarkInfo(
        code="RM6",
        uuid=MARK_RM6_UUID,
        name="Race Mark 6",
        role="Bottom Gate Starboard / Start & Finish",
        color="#ff282e",
        target_lat=40.80032415,
        target_lon=14.23089874,
    ),
    "RM7": MarkInfo(
        code="RM7",
        uuid=MARK_RM7_UUID,
        name="Race Mark 7",
        role="Start Line Starboard / Bottom Gate Starboard",
        color="#fff700",
        target_lat=40.8020,
        target_lon=14.2290,
    ),
    "RM8": MarkInfo(
        code="RM8",
        uuid=MARK_RM8_UUID,
        name="Race Mark 8",
        role="Bottom Gate Port / Start & Finish",
        color="#eeff00",
        target_lat=40.80297685,
        target_lon=14.22666341,
    ),
}


def get_venue_projection(venue: str | None) -> Tuple[float, float, float, float]:
    """Returns (lat0, lon0, k_lat, k_lon) for the given venue or race identifier."""
    if venue and any(token in venue.lower() for token in ("cagliari", "cag")):
        return (CAGLIARI_LAT0, CAGLIARI_LON0, CAGLIARI_K_LAT, CAGLIARI_K_LON)
    return (LAT0, LON0, K_LAT, K_LON)


OFFICIAL_WIND_ASSET_ID: Final[str] = "0a18270a-3758-46e8-9a5e-3b441051674f"


@dataclass(frozen=True)
class CompetitorInfo:
    code: str
    uuid: str
    name: str
    official_name: str
    color: str


COMPETITORS: Final[Dict[str, CompetitorInfo]] = {
    "42e39310-fef5-4c5d-b099-a599aad5ddbb": CompetitorInfo(
        code="FRA",
        uuid="42e39310-fef5-4c5d-b099-a599aad5ddbb",
        name="Orient Express Racing Team",
        official_name="La Roche-Posay Racing Team",
        color="#ff80c0",
    ),
    "80d4cda4-17f5-4bcf-b7fd-5fc0f39f3d60": CompetitorInfo(
        code="NZL G",
        uuid="80d4cda4-17f5-4bcf-b7fd-5fc0f39f3d60",
        name="Emirates Team NZ Women & Youth",
        official_name="Emirates Team New Zealand Women and Youth",
        color="#ff0000",
    ),
    "4f5369cd-0fa3-4241-afd2-00f356898e22": CompetitorInfo(
        code="ITA B",
        uuid="4f5369cd-0fa3-4241-afd2-00f356898e22",
        name="Luna Rossa Prada Pirelli",
        official_name="Luna Rossa",
        color="#26e8fd",
    ),
    "126368d2-98e9-4c3e-97ce-fb047d40ab0e": CompetitorInfo(
        code="USA",
        uuid="126368d2-98e9-4c3e-97ce-fb047d40ab0e",
        name="American Magic",
        official_name="American Racing Challenger Team USA",
        color="#36d8e4",
    ),
    "130ac4af-df5a-4568-af62-9d9395df9e9e": CompetitorInfo(
        code="ITA G",
        uuid="130ac4af-df5a-4568-af62-9d9395df9e9e",
        name="Luna Rossa Women & Youth",
        official_name="Luna Rossa Women and Youth",
        color="#ff8000",
    ),
    "0890cbf9-fc5e-4187-8eee-0bf59e9f05e4": CompetitorInfo(
        code="GBR G",
        uuid="0890cbf9-fc5e-4187-8eee-0bf59e9f05e4",
        name="INEOS Britannia Women & Youth",
        official_name="Ineos Britannia Women and Youth",
        color="#ffd700",
    ),
    "f7a7d97a-040e-4ad5-af0f-ae6ff7b51cea": CompetitorInfo(
        code="NZL B",
        uuid="f7a7d97a-040e-4ad5-af0f-ae6ff7b51cea",
        name="Emirates Team New Zealand",
        official_name="Emirates Team New Zealand",
        color="#00b700",
    ),
    "ed5d37be-52fa-4902-b190-757027017085": CompetitorInfo(
        code="SUI",
        uuid="ed5d37be-52fa-4902-b190-757027017085",
        name="Alinghi Red Bull Racing",
        official_name="Tudor Team Alinghi",
        color="#ffff00",
    ),
    "f535f0dc-a45b-4668-ae07-bd52e0cdd947": CompetitorInfo(
        code="GBR B",
        uuid="f535f0dc-a45b-4668-ae07-bd52e0cdd947",
        name="INEOS Britannia",
        official_name="Ineos Britannia",
        color="#8e8eff",
    ),
}

CODE_TO_COMPETITOR: Final[Dict[str, CompetitorInfo]] = {
    info.code: info for info in COMPETITORS.values()
}

UUID_TO_CODE: Final[Dict[str, str]] = {
    uuid: info.code for uuid, info in COMPETITORS.items()
}

CODE_TO_UUID: Final[Dict[str, str]] = {
    info.code: uuid for uuid, info in COMPETITORS.items()
}
