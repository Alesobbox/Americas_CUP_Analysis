"""Versioned AC38 polar definitions and selection settings."""

POLAR_SCHEMA_VERSION = "2.0"
POLAR_METHOD_VERSION = "polar-2"
POLAR_BOOTSTRAP_DRAWS = 500
POLAR_BOOTSTRAP_SEED = 20261119

STEADY_MIN_SOG_KT = 5.0
STEADY_MAX_SOG_KT = 50.0
STEADY_MIN_TWS_KT = 2.0
STEADY_MAX_TWS_KT = 35.0
UPWIND_ABS_TWA_RANGE = (28.0, 75.0)
DOWNWIND_ABS_TWA_RANGE = (105.0, 172.0)
MANOEUVRE_EXCLUSION_DEFAULT_MS = 6500
GATE_EXCLUSION_MS = 8000
MAX_STEADY_TURN_RATE_DEG_S = 6.0
MIN_COMPETITOR_SEPARATION_M = 60.0

TWS_BIN_STEP_KT = 1.0
TWA_BIN_STEP_DEG = 2.5
KERNEL_BW_TWS_KT = 1.5
KERNEL_BW_TWA_DEG = 4.0
HIST_MIN_KT = -5.0
HIST_STEP_KT = 0.25
HIST_N_BINS = 280
MIN_CURVE_SUPPORT_S = 12.0
MIN_CURVE_CLUSTERS = 2

POLAR_CAVEATS = [
    "Observed ground-speed polar: SOG includes surface current and cannot separate water speed from tidal or residual flow.",
    "Conditional residuals also include tactics, traffic, sea state, and wind-measurement error; they cannot isolate crew or flight-control skill.",
    "The conditional 90th percentile (p90) is an observed upper conditional percentile, not a proven optimal target.",
    "Tack is a quadratic-adjusted fixed-effect contrast; its estimator is refitted in every day-block draw.",
    "LODO assesses retrospective transfer between days; chronological scores use only earlier days.",
    "Full-archive curves are descriptive fits; validation scores and residuals use held-out observations.",
    "Eight or fewer independent days limit uncertainty and subgroup calibration evidence.",
]

POLAR_DEFINITIONS = {
    "polar_sog_mean_kt": {
        "label": "Observed conditional mean ground speed",
        "unit": "kt",
        "formula": "Kernel-smoothed conditional mean steady-state SOG(TWS, |TWA|, mode) + fixed-effect tack contrast (SOG includes surface current)",
        "window": "steady-state 1 Hz samples on completed active legs",
        "denominator": "valid steady-state seconds (excludes ±6.5 s manoeuvres, ±8 s gates, >6°/s turns, <60 m traffic)",
        "source": "interpolated 1 Hz SOG, heading, COG, TWD, and TWS within validated source coverage",
    },
    "polar_sog_p50_kt": {
        "label": "Observed conditional median ground speed (50th percentile)",
        "unit": "kt",
        "formula": "Kernel-weighted conditional 50th percentile of steady-state SOG(TWS, |TWA|, mode) + fixed-effect tack contrast",
        "window": "steady-state 1 Hz samples on completed active legs",
        "denominator": "valid steady-state seconds with >=12 s kernel support across >=2 boat-leg clusters",
        "source": "observed steady-state SOG; descriptive quantile, not a physical VPP prediction",
    },
    "polar_sog_p90_kt": {
        "label": "Observed upper conditional percentile (90th percentile)",
        "unit": "kt",
        "formula": "Kernel-weighted conditional 90th percentile of steady-state SOG(TWS, |TWA|, mode) + fixed-effect tack contrast",
        "window": "steady-state 1 Hz samples on completed active legs",
        "denominator": "valid steady-state seconds with >=12 s kernel support across >=2 boat-leg clusters",
        "source": "observed steady-state SOG; observed upper conditional percentile, not a proven optimal target",
    },
    "sog_residual_kt": {
        "label": "Conditional ground-speed residual",
        "unit": "kt",
        "formula": "Observed steady-state SOG minus conditional expected ground speed under Day-Grouped (LODO) or Leave-One-Race-Out (LORO) cross-validation",
        "window": "steady-state 1 Hz samples on completed active legs",
        "denominator": "boat steady-state coverage seconds; 95% intervals are day-block bootstrap confidence intervals",
        "source": "steady-state SOG, TWS, |TWA|, and tack; reflects current, tactics, traffic, sea state, and wind error alongside boat speed",
    },
    "wind_vmg_residual_kt": {
        "label": "Conditional wind-VMG residual",
        "unit": "kt",
        "formula": "Observed steady-state wind-relative VMG minus conditional expected wind-VMG(TWS, |TWA|, tack)",
        "window": "steady-state 1 Hz samples on completed active legs",
        "denominator": "boat steady-state coverage seconds; 95% intervals are day-block bootstrap confidence intervals",
        "source": "steady-state SOG, COG, TWD, TWS, heading; reflects current, wind-angle choices, and measurement noise",
    },
    "tack_fixed_effect_kt": {
        "label": "Fixed-effect tack contrast (Starboard − Port)",
        "unit": "kt",
        "formula": "Weighted OLS contrast coefficient on two-category fixed effect I_stbd (+0.5 STARBOARD, -0.5 PORT) controlling for bivariate quadratic (TWS, |TWA|)",
        "window": "all steady-state 1 Hz samples within mode",
        "denominator": "valid steady-state seconds; 95% CI from 500 day-block bootstrap draws",
        "source": "signed TWA derived from boat heading and TWD; reflects persistent current/wave/sensor asymmetry across tacks",
    },
}

ARCHIVE_TWS_BRACKETS = (
    ("6_9", "6–9 kt TWS", 6.0, 9.0, 7.5),
    ("9_12", "9–12 kt TWS", 9.0, 12.0, 10.5),
    ("12_15", "12–15 kt TWS", 12.0, 15.0, 13.5),
    ("15_20", "15–20 kt TWS", 15.0, 20.0, 17.0),
)
