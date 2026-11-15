"""The Codex-reviewed synthetic fixture table, transcribed as the independent oracle.

Columns: id, lat, lon, set, role, expected group (-1 noise, "0|1" ambiguous), grid, shifted.
Role values: core, border, noise, ambiguous (non-core border within eps of two core components).
Labels encode construction intent only; no label applies to any real USGS record.
"""

AMBIG = "0|1"

TABLE = [
    ("fx-amb-l1", 40.70, 120.20, "AMB", "core", 0, "G26_60", "S26_60"),
    ("fx-amb-l2", 39.70, 120.20, "AMB", "core", 0, "G25_60", "S26_60"),
    ("fx-amb-l3", 38.80, 120.20, "AMB", "core", 0, "G25_60", "S26_60"),
    ("fx-amb-l4", 37.80, 120.20, "AMB", "border", 0, "G25_60", "S26_60"),
    ("fx-amb-r1", 44.30, 120.20, "AMB", "core", 1, "G26_60", "S27_60"),
    ("fx-amb-r2", 45.30, 120.20, "AMB", "core", 1, "G27_60", "S27_60"),
    ("fx-amb-r3", 46.20, 120.20, "AMB", "core", 1, "G27_60", "S27_60"),
    ("fx-amb-r4", 47.20, 120.20, "AMB", "border", 1, "G27_60", "S27_60"),
    ("fx-amb-z", 42.50, 120.20, "AMB", "ambiguous", AMBIG, "G26_60", "S27_60"),
    ("fx-chain-1", 0.50, 50.20, "CHAIN", "core", 2, "G18_46", "S18_46"),
    ("fx-chain-2", 1.40, 50.20, "CHAIN", "core", 2, "G18_46", "S18_46"),
    ("fx-chain-3", 2.30, 50.20, "CHAIN", "core", 2, "G18_46", "S18_46"),
    ("fx-chain-4", 3.20, 50.20, "CHAIN", "core", 2, "G18_46", "S19_46"),
    ("fx-chain-5", 4.10, 50.20, "CHAIN", "border", 2, "G18_46", "S19_46"),
    ("fx-chain-x", 6.80, 50.20, "CHAIN", "noise", -1, "G19_46", "S19_46"),
    ("fx-chain-y", -1.30, 50.20, "CHAIN", "border", 2, "G17_46", "S18_46"),
    ("fx-dateline-1", -15.20, 179.60, "DATELINE", "core", 3, "G14_71", "S15_00"),
    ("fx-dateline-2", -15.40, 179.90, "DATELINE", "core", 3, "G14_71", "S15_00"),
    ("fx-dateline-3", -15.30, -179.80, "DATELINE", "core", 3, "G14_00", "S15_00"),
    ("fx-dateline-4", -15.10, -179.50, "DATELINE", "core", 3, "G14_00", "S15_00"),
    ("fx-dateline-5", -15.25, 180.00, "DATELINE", "core", 3, "G14_00", "S15_00"),
    ("fx-dense-a1", 12.00, 22.00, "DENSE-A", "core", 4, "G20_40", "S20_40"),
    ("fx-dense-a2", 12.20, 22.10, "DENSE-A", "core", 4, "G20_40", "S20_40"),
    ("fx-dense-a3", 12.10, 22.30, "DENSE-A", "core", 4, "G20_40", "S20_40"),
    ("fx-dense-a4", 12.05, 22.20, "DENSE-A", "core", 4, "G20_40", "S20_40"),
    ("fx-dense-a5", 12.30, 21.90, "DENSE-A", "core", 4, "G20_40", "S20_40"),
    ("fx-dense-a6", 12.40, 22.40, "DENSE-A", "core", 4, "G20_40", "S20_40"),
    ("fx-dense-b1", -33.40, -69.60, "DENSE-B", "core", 5, "G11_22", "S11_22"),
    ("fx-dense-b2", -33.20, -69.40, "DENSE-B", "core", 5, "G11_22", "S11_22"),
    ("fx-dense-b3", -33.30, -69.20, "DENSE-B", "core", 5, "G11_22", "S11_22"),
    ("fx-dense-b4", -33.10, -69.50, "DENSE-B", "core", 5, "G11_22", "S11_22"),
    ("fx-dense-b5", -33.45, -69.30, "DENSE-B", "core", 5, "G11_22", "S11_22"),
    ("fx-edge-1", 0.00, 0.00, "EDGE", "noise", -1, "G18_36", "S18_36"),
    ("fx-edge-2", 10.00, -110.00, "EDGE", "noise", -1, "G20_14", "S20_14"),
    ("fx-edge-3", 14.9999, -65.0001, "EDGE", "noise", -1, "G20_22", "S21_23"),
    ("fx-edge-4", 15.00, -65.00, "EDGE", "noise", -1, "G21_23", "S21_23"),
    ("fx-edge-5", -50.00, -180.00, "EDGE", "noise", -1, "G08_00", "S08_00"),
    ("fx-iso-1", 45.50, 100.50, "ISO", "noise", -1, "G27_56", "S27_56"),
    ("fx-iso-2", -60.20, 10.30, "ISO", "noise", -1, "G05_38", "S06_38"),
    ("fx-npole-1", 89.50, 0.00, "NPOLE", "core", 6, "G35_36", "S36_36"),
    ("fx-npole-2", 89.50, 90.00, "NPOLE", "core", 6, "G35_54", "S36_54"),
    ("fx-npole-3", 89.50, 180.00, "NPOLE", "core", 6, "G35_00", "S36_00"),
    ("fx-npole-4", 89.50, -90.00, "NPOLE", "core", 6, "G35_18", "S36_18"),
    ("fx-npole-5", 90.00, 0.00, "NPOLE", "core", 6, "G35_36", "S36_36"),
    ("fx-ord-A", -25.50, 140.50, "ORDER", "noise", -1, "G12_64", "S13_64"),
    ("fx-ord-a", 35.50, -80.50, "ORDER", "noise", -1, "G25_19", "S25_20"),
    ("fx-ord-é", -5.50, -100.50, "ORDER", "noise", -1, "G16_15", "S17_16"),
    ("fx-ord-～", 65.50, 20.50, "ORDER", "noise", -1, "G31_40", "S31_40"),
    ("fx-ord-\U0001f30b", -40.50, 70.50, "ORDER", "noise", -1, "G09_50", "S10_50"),
    ("fx-small-1", -45.50, -30.50, "SMALL", "noise", -1, "G08_29", "S09_30"),
    ("fx-small-2", -45.60, -30.40, "SMALL", "noise", -1, "G08_29", "S09_30"),
    ("fx-small-3", -45.40, -30.60, "SMALL", "noise", -1, "G08_29", "S09_30"),
    ("fx-spole-1", -89.50, 30.00, "SPOLE", "core", 7, "G00_42", "S00_42"),
    ("fx-spole-2", -89.50, 120.00, "SPOLE", "core", 7, "G00_60", "S00_60"),
    ("fx-spole-3", -89.50, -150.00, "SPOLE", "core", 7, "G00_06", "S00_06"),
    ("fx-spole-4", -90.00, 0.00, "SPOLE", "core", 7, "G00_36", "S00_36"),
]

NOISE_IDS = sorted(r[0] for r in TABLE if r[5] == -1)
GROUP_COUNT = 8
