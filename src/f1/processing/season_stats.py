"""Agregacoes de temporada sobre o Top N de voltas de cada GP.

Funcoes puras, sem I/O: recebem os resultados ja calculados por GP e devolvem
estruturas prontas para os graficos e indicadores do dashboard.
"""

from collections import Counter
from dataclasses import dataclass

from f1.domain.models import FastestLapEntry


@dataclass(frozen=True)
class CountItem:
    label: str
    detail: str
    colour: str
    count: int


@dataclass(frozen=True)
class MeetingGap:
    meeting_name: str
    gap: float


def gaps_to_leader(entries: list[FastestLapEntry]) -> list[float]:
    """Diferenca (s) de cada volta para a mais rapida da lista."""
    if not entries:
        return []
    best = min(e.lap_duration for e in entries)
    return [round(e.lap_duration - best, 3) for e in entries]


def team_top_counts(
    results: dict[str, list[FastestLapEntry]],
) -> list[CountItem]:
    """Quantas vezes cada equipe aparece no Top N, somando todos os GPs."""
    counts: Counter[str] = Counter()
    colours: dict[str, str] = {}
    for entries in results.values():
        for entry in entries:
            counts[entry.team_name] += 1
            colours.setdefault(entry.team_name, entry.team_colour)
    return [
        CountItem(label=team, detail=team, colour=colours[team], count=n)
        for team, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    ]


def driver_p1_counts(
    results: dict[str, list[FastestLapEntry]],
) -> list[CountItem]:
    """Quantas vezes cada piloto fez a volta mais rapida (P1) de um GP."""
    counts: Counter[str] = Counter()
    info: dict[str, FastestLapEntry] = {}
    for entries in results.values():
        leader = next((e for e in entries if e.rank == 1), None)
        if leader is None:
            continue
        counts[leader.driver_acronym] += 1
        info.setdefault(leader.driver_acronym, leader)
    return [
        CountItem(
            label=acronym,
            detail=info[acronym].driver_name,
            colour=info[acronym].team_colour,
            count=n,
        )
        for acronym, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    ]


def spread_per_meeting(
    results: dict[str, list[FastestLapEntry]],
) -> list[MeetingGap]:
    """Diferenca entre o primeiro e o ultimo do Top N em cada GP (ordem mantida)."""
    spreads = []
    for meeting_name, entries in results.items():
        if len(entries) < 2:
            continue
        durations = [e.lap_duration for e in entries]
        spreads.append(
            MeetingGap(meeting_name, round(max(durations) - min(durations), 3))
        )
    return spreads


def format_lap_time(seconds: float) -> str:
    """Formata segundos como m:ss.mmm."""
    minutes = int(seconds // 60)
    return f"{minutes}:{seconds - minutes * 60:06.3f}"
