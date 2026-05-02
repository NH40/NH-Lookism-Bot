PHASE_RANK_WEIGHTS: dict[str, dict[str, int]] = {
    "gang": {
        "F": 40, "E": 30, "D": 20, "C": 8, "B": 2,
    },
    "king": {
        "C": 35, "B": 30, "A": 20, "S": 10, "SS": 5,
    },
    "fist": {
        "A": 20, "S": 20, "SS": 20, "SSS": 15, "SR": 10, "SSR": 8, "UR": 5, "LR": 2,
    },
    "emperor": {
        "MP": 30, "X": 25, "XX": 20, "XXX": 15, "DX": 7, "ERROR": 3,
    },
}