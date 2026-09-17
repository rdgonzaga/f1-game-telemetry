"""Readable names for track, session type and formula ids (shared by formats 2025 and 2026)."""

from __future__ import annotations

TRACKS: dict[int, str] = {
    0: "Melbourne",
    2: "Shanghai",
    3: "Sakhir",
    4: "Catalunya",
    5: "Monaco",
    6: "Montreal",
    7: "Silverstone",
    9: "Hungaroring",
    10: "Spa-Francorchamps",
    11: "Monza",
    12: "Singapore",
    13: "Suzuka",
    14: "Abu Dhabi",
    15: "Austin",
    16: "Interlagos",
    17: "Red Bull Ring",
    19: "Mexico City",
    20: "Baku",
    26: "Zandvoort",
    27: "Imola",
    29: "Jeddah",
    30: "Miami",
    31: "Las Vegas",
    32: "Lusail",
    39: "Silverstone (Reverse)",
    40: "Red Bull Ring (Reverse)",
    41: "Zandvoort (Reverse)",
    42: "Madrid",
}

SESSION_TYPES: dict[int, str] = {
    0: "Unknown",
    1: "Practice 1",
    2: "Practice 2",
    3: "Practice 3",
    4: "Short Practice",
    5: "Qualifying 1",
    6: "Qualifying 2",
    7: "Qualifying 3",
    8: "Short Qualifying",
    9: "One-Shot Qualifying",
    10: "Sprint Shootout 1",
    11: "Sprint Shootout 2",
    12: "Sprint Shootout 3",
    13: "Short Sprint Shootout",
    14: "One-Shot Sprint Shootout",
    15: "Race",
    16: "Race 2",
    17: "Race 3",
    18: "Time Trial",
}

FORMULAS: dict[int, str] = {
    0: "F1 Modern",
    1: "F1 Classic",
    2: "F2",
    3: "F1 Generic",
    4: "Beta",
    6: "Esports",
    8: "F1 World",
    9: "F1 Elimination",
    13: "F1 26",
}

FORMULA_F2 = 2


def track_name(track_id: int) -> str:
    return TRACKS.get(track_id, f"Unknown track ({track_id})")


def session_type_name(session_type: int) -> str:
    return SESSION_TYPES.get(session_type, f"Unknown session ({session_type})")


def formula_name(formula: int) -> str:
    return FORMULAS.get(formula, f"Unknown formula ({formula})")


# Visual compound is what the game shows; actual compound is the C-rating. The same id means different tyres in each.
VISUAL_TYRE_COMPOUNDS: dict[int, str] = {
    7: "Inter",
    8: "Wet",
    9: "Classic Dry",
    10: "Classic Wet",
    15: "F2 Wet",
    16: "Soft",
    17: "Medium",
    18: "Hard",
    19: "F2 Super Soft",
    20: "F2 Soft",
    21: "F2 Medium",
    22: "F2 Hard",
}

ACTUAL_TYRE_COMPOUNDS: dict[int, str] = {
    7: "Inter",
    8: "Wet",
    9: "Classic Dry",
    10: "Classic Wet",
    11: "F2 Super Soft",
    12: "F2 Soft",
    13: "F2 Medium",
    14: "F2 Hard",
    15: "F2 Wet",
    16: "C5",
    17: "C4",
    18: "C3",
    19: "C2",
    20: "C1",
    21: "C0",
    22: "C6",
}

# Mode 3 is Overtake in format 2025 and Boost in format 2026.
ERS_DEPLOY_MODES: dict[int, dict[int, str]] = {
    2025: {0: "None", 1: "Medium", 2: "Hotlap", 3: "Overtake"},
    2026: {0: "None", 1: "Medium", 2: "Hotlap", 3: "Boost"},
}


def visual_tyre_compound_name(compound: int) -> str:
    return VISUAL_TYRE_COMPOUNDS.get(compound, f"Unknown compound ({compound})")


def actual_tyre_compound_name(compound: int) -> str:
    return ACTUAL_TYRE_COMPOUNDS.get(compound, f"Unknown compound ({compound})")


def ers_deploy_mode_name(mode: int, packet_format: int) -> str:
    return ERS_DEPLOY_MODES.get(packet_format, {}).get(mode, f"Unknown mode ({mode})")
