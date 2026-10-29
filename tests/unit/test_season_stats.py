from f1.domain.models import FastestLapEntry
from f1.processing.season_stats import (
    driver_p1_counts,
    format_lap_time,
    gaps_to_leader,
    spread_per_meeting,
    team_top_counts,
)


def _entry(rank: int, acronym: str, team: str, duration: float) -> FastestLapEntry:
    return FastestLapEntry(
        rank=rank,
        driver_name=f"Driver {acronym}",
        driver_acronym=acronym,
        team_name=team,
        team_colour="FF0000" if team == "Ferrari" else "3671C6",
        lap_number=10,
        lap_duration=duration,
    )


def _results() -> dict[str, list[FastestLapEntry]]:
    return {
        "Bahrain GP": [
            _entry(1, "VER", "Red Bull", 92.0),
            _entry(2, "LEC", "Ferrari", 92.5),
            _entry(3, "SAI", "Ferrari", 93.0),
        ],
        "Monaco GP": [
            _entry(1, "LEC", "Ferrari", 74.0),
            _entry(2, "VER", "Red Bull", 74.2),
        ],
        "Imola GP": [
            _entry(1, "VER", "Red Bull", 78.0),
        ],
        "Empty GP": [],
    }


def test_gaps_to_leader() -> None:
    entries = _results()["Bahrain GP"]
    assert gaps_to_leader(entries) == [0.0, 0.5, 1.0]


def test_gaps_to_leader_empty() -> None:
    assert gaps_to_leader([]) == []


def test_team_top_counts_sorted_desc() -> None:
    result = team_top_counts(_results())
    # empate em 3 -> desempata por nome
    assert [(c.label, c.count) for c in result] == [("Ferrari", 3), ("Red Bull", 3)]
    assert result[0].colour == "FF0000"


def test_driver_p1_counts() -> None:
    result = driver_p1_counts(_results())
    assert [(c.label, c.count) for c in result] == [("VER", 2), ("LEC", 1)]
    assert result[0].detail == "Driver VER"


def test_spread_per_meeting_skips_short_lists() -> None:
    result = spread_per_meeting(_results())
    assert [(m.meeting_name, m.gap) for m in result] == [
        ("Bahrain GP", 1.0),
        ("Monaco GP", 0.2),
    ]


def test_format_lap_time() -> None:
    assert format_lap_time(92.345) == "1:32.345"
    assert format_lap_time(59.9) == "0:59.900"
