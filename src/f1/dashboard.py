import html

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from f1.domain.models import FastestLapEntry
from f1.domain.services import F1DashboardService
from f1.ingestion.http_client import HttpClient
from f1.ingestion.openf1_client import (
    OpenF1DriverRepository,
    OpenF1LapRepository,
    OpenF1MeetingRepository,
    OpenF1SessionRepository,
)
from f1.processing.season_stats import (
    driver_p1_counts,
    format_lap_time,
    gaps_to_leader,
    spread_per_meeting,
    team_top_counts,
)
from f1.utils.config import DEFAULT_YEAR

YEARS = [2023, 2024, 2025]
SESSION_LABELS = {"Race": "Corrida", "Qualifying": "Classificação"}

# Paleta neon da interface (acentos de UI, nao identidade de dados).
NEON_PINK = "#FF2E88"
NEON_ORANGE = "#FF8A00"
NEON_VIOLET = "#9B5CFF"
NEON_CYAN = "#22D3EE"
INK = "#EDEDF7"
INK_MUTED = "#9A9AB8"
GRID = "rgba(255,255,255,0.06)"
FALLBACK_TEAM = "#8A8AA3"

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Titillium+Web:wght@400;600;700;900&display=swap');

html, body, [class*="css"], .stApp, button, input, select, textarea {{
    font-family: 'Titillium Web', sans-serif;
}}
.stApp {{
    background:
        radial-gradient(1200px 600px at 10% -10%, rgba(155,92,255,0.18), transparent 60%),
        radial-gradient(900px 500px at 100% 0%, rgba(255,46,136,0.14), transparent 60%),
        radial-gradient(800px 600px at 50% 120%, rgba(255,138,0,0.10), transparent 60%),
        #0B0B14;
}}
[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stSidebar"] {{
    background: linear-gradient(180deg, #14142A 0%, #0E0E1C 100%);
    border-right: 1px solid rgba(255,255,255,0.06);
}}
.block-container {{ padding-top: 2.2rem; max-width: 1400px; }}

.hero {{ margin-bottom: 1.6rem; }}
.hero .kicker {{
    display: inline-block; padding: 4px 12px; border-radius: 999px;
    font-size: 0.75rem; font-weight: 700; letter-spacing: .12em; text-transform: uppercase;
    color: {INK}; background: linear-gradient(90deg, {NEON_PINK}, {NEON_ORANGE});
}}
.hero h1 {{
    font-size: 2.8rem; font-weight: 900; line-height: 1.05; margin: .6rem 0 .3rem 0;
    background: linear-gradient(90deg, #FFFFFF 0%, #FFB3D5 45%, {NEON_ORANGE} 100%);
    -webkit-background-clip: text; background-clip: text; color: transparent;
}}
.hero p {{ color: {INK_MUTED}; font-size: 1.05rem; margin: 0; }}

.kpi {{
    position: relative; padding: 18px 20px 16px 20px; border-radius: 16px;
    background: rgba(20,20,42,0.85); border: 1px solid rgba(255,255,255,0.07);
    overflow: hidden; height: 100%;
}}
.kpi::before {{
    content: ""; position: absolute; inset: 0 0 auto 0; height: 3px;
    background: var(--accent);
}}
.kpi::after {{
    content: ""; position: absolute; right: -40px; top: -40px; width: 120px; height: 120px;
    border-radius: 50%; background: var(--accent); opacity: .16; filter: blur(30px);
}}
.kpi .label {{
    color: {INK_MUTED}; font-size: .78rem; font-weight: 700;
    letter-spacing: .1em; text-transform: uppercase;
}}
.kpi .value {{ color: {INK}; font-size: 2.1rem; font-weight: 700; line-height: 1.15; margin-top: 6px; }}
.kpi .detail {{ color: {INK_MUTED}; font-size: .9rem; margin-top: 2px; }}
.kpi .dot {{
    display: inline-block; width: 9px; height: 9px; border-radius: 50%;
    margin-right: 6px; vertical-align: middle;
}}

.section-title {{
    display: flex; align-items: center; gap: 10px;
    color: {INK}; font-size: 1.25rem; font-weight: 700; margin: 2rem 0 .2rem 0;
}}
.section-title::before {{
    content: ""; width: 4px; height: 20px; border-radius: 2px;
    background: linear-gradient(180deg, {NEON_PINK}, {NEON_ORANGE});
}}
.section-sub {{ color: {INK_MUTED}; font-size: .92rem; margin-bottom: .8rem; }}

div[data-testid="stPlotlyChart"] {{
    background: rgba(20,20,42,0.85); border: 1px solid rgba(255,255,255,0.07);
    border-radius: 16px; padding: 6px 8px;
}}

.board {{
    background: rgba(20,20,42,0.85); border: 1px solid rgba(255,255,255,0.07);
    border-radius: 16px; padding: 10px 6px;
}}
.row {{
    display: grid; grid-template-columns: 44px 6px 1fr auto; align-items: center;
    gap: 12px; padding: 10px 14px; border-radius: 12px;
}}
.row + .row {{ border-top: 1px solid rgba(255,255,255,0.05); }}
.row .pos {{
    width: 36px; height: 36px; border-radius: 10px; display: grid; place-items: center;
    font-weight: 900; color: {INK}; background: rgba(255,255,255,0.06);
}}
.row.p1 .pos {{ background: linear-gradient(135deg, {NEON_PINK}, {NEON_ORANGE}); }}
.row .stripe {{ width: 6px; height: 36px; border-radius: 3px; }}
.row .name {{ color: {INK}; font-weight: 700; font-size: 1.02rem; line-height: 1.2; }}
.row .team {{ color: {INK_MUTED}; font-size: .85rem; }}
.row .time {{ text-align: right; color: {INK}; font-weight: 700; font-variant-numeric: tabular-nums; }}
.row .gap {{ text-align: right; color: {INK_MUTED}; font-size: .85rem; font-variant-numeric: tabular-nums; }}
.row.p1 .gap {{ color: {NEON_ORANGE}; }}
</style>
"""


@st.cache_resource
def get_service() -> F1DashboardService:
    client = HttpClient()
    return F1DashboardService(
        meeting_repo=OpenF1MeetingRepository(client),
        session_repo=OpenF1SessionRepository(client),
        lap_repo=OpenF1LapRepository(client),
        driver_repo=OpenF1DriverRepository(client),
    )


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_meetings(year: int) -> list[dict]:
    meetings = get_service().get_meetings_for_year(year)
    return [m.model_dump() for m in meetings]


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_top_laps(meeting_key: int, session_name: str) -> list[dict]:
    entries = get_service().get_top_laps_for_meeting(meeting_key, session_name)
    return [e.model_dump() for e in entries]


def team_hex(colour: str | None) -> str:
    colour = (colour or "").strip().lstrip("#")
    return f"#{colour}" if len(colour) == 6 else FALLBACK_TEAM


def style_figure(fig: go.Figure, height: int) -> go.Figure:
    fig.update_layout(
        height=height,
        margin={"l": 10, "r": 30, "t": 10, "b": 10},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Titillium Web, sans-serif", "color": INK_MUTED, "size": 13},
        hoverlabel={
            "bgcolor": "#1C1C36",
            "bordercolor": "#2E2E52",
            "font": {"color": INK, "family": "Titillium Web, sans-serif"},
        },
        showlegend=False,
    )
    fig.update_xaxes(gridcolor=GRID, zeroline=False, linecolor=GRID)
    fig.update_yaxes(gridcolor=GRID, zeroline=False, linecolor=GRID)
    return fig


def kpi(
    label: str, value: str, detail: str, accent: str, dot: str | None = None
) -> str:
    dot_html = f'<span class="dot" style="background:{dot}"></span>' if dot else ""
    return (
        f'<div class="kpi" style="--accent:{accent}">'
        f'<div class="label">{html.escape(label)}</div>'
        f'<div class="value">{html.escape(value)}</div>'
        f'<div class="detail">{dot_html}{html.escape(detail)}</div>'
        "</div>"
    )


def section(title: str, subtitle: str = "") -> None:
    sub = f'<div class="section-sub">{html.escape(subtitle)}</div>' if subtitle else ""
    st.markdown(
        f'<div class="section-title">{html.escape(title)}</div>{sub}',
        unsafe_allow_html=True,
    )


def count_bar_chart(
    items: list, axis_title: str, hover_label: str, height: int
) -> go.Figure:
    items = list(reversed(items))  # maior no topo
    fig = go.Figure(
        go.Bar(
            x=[i.count for i in items],
            y=[i.label for i in items],
            orientation="h",
            marker={
                "color": [team_hex(i.colour) for i in items],
                "cornerradius": 4,
            },
            text=[i.count for i in items],
            textposition="outside",
            textfont={"color": INK},
            customdata=[i.detail for i in items],
            hovertemplate="<b>%{customdata}</b><br>"
            + hover_label
            + ": %{x}<extra></extra>",
            cliponaxis=False,
        )
    )
    fig.update_layout(bargap=0.35)
    top = max((i.count for i in items), default=1)
    fig.update_xaxes(
        title=axis_title,
        range=[0, top * 1.15],
        dtick=1 if top <= 10 else None,
    )
    fig.update_yaxes(showgrid=False, tickfont={"color": INK})
    return style_figure(fig, height=height)


def spread_chart(spreads: list) -> go.Figure:
    names = [s.meeting_name.replace(" Grand Prix", " GP") for s in spreads]
    gaps = [s.gap for s in spreads]
    fig = go.Figure(
        go.Scatter(
            x=names,
            y=gaps,
            mode="lines+markers",
            line={"color": NEON_PINK, "width": 2, "shape": "linear"},
            marker={
                "size": 9,
                "color": NEON_PINK,
                "line": {"color": "#0B0B14", "width": 2},
            },
            fill="tozeroy",
            fillgradient={
                "type": "vertical",
                "colorscale": [
                    [0, "rgba(255,46,136,0)"],
                    [1, "rgba(255,46,136,0.35)"],
                ],
            },
            hovertemplate="<b>%{x}</b><br>P1 → P5: %{y:.3f} s<extra></extra>",
        )
    )
    fig.update_xaxes(showgrid=False, tickangle=-35)
    fig.update_yaxes(title="segundos", rangemode="tozero")
    return style_figure(fig, height=340)


def gap_chart(df: pd.DataFrame) -> go.Figure:
    df = df.iloc[::-1]
    fig = go.Figure(
        go.Bar(
            x=df["gap"],
            y=df["driver_acronym"],
            orientation="h",
            marker={"color": df["colour"].tolist(), "cornerradius": 4},
            text=[f"+{g:.3f}" if g > 0 else "líder" for g in df["gap"]],
            textposition="outside",
            textfont={"color": INK},
            customdata=df[["driver_name", "time"]].to_numpy(),
            hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]}"
            "<br>+%{x:.3f} s<extra></extra>",
            cliponaxis=False,
        )
    )
    fig.update_layout(bargap=0.35)
    fig.update_xaxes(
        title="diferença para o P1 (s)", range=[0, max(df["gap"].max(), 0.1) * 1.25]
    )
    fig.update_yaxes(showgrid=False, tickfont={"color": INK})
    return style_figure(fig, height=330)


def leaderboard(df: pd.DataFrame) -> str:
    rows = []
    for _, r in df.iterrows():
        gap = "Volta mais rápida" if r["gap"] == 0 else f"+{r['gap']:.3f} s"
        rows.append(
            f'<div class="row {"p1" if r["rank"] == 1 else ""}">'
            f'<div class="pos">{int(r["rank"])}</div>'
            f'<div class="stripe" style="background:{r["colour"]}"></div>'
            f'<div><div class="name">{html.escape(r["driver_name"])}</div>'
            f'<div class="team">{html.escape(r["team_name"])}'
            f" &middot; volta {int(r['lap_number'])}</div></div>"
            f'<div><div class="time">{r["time"]}</div>'
            f'<div class="gap">{gap}</div></div>'
            "</div>"
        )
    return f'<div class="board">{"".join(rows)}</div>'


def load_season(meetings: list[dict], session_name: str) -> tuple[dict, int]:
    """Busca o Top N de cada GP. Retorna {nome_do_gp: [entries]} e n de falhas."""
    results: dict[str, list[FastestLapEntry]] = {}
    failures = 0
    progress = st.progress(0.0, text="Carregando dados da temporada...")
    for i, meeting in enumerate(meetings, start=1):
        try:
            raw = fetch_top_laps(meeting["meeting_key"], session_name)
        except Exception:  # um GP com erro nao derruba a pagina
            failures += 1
            raw = []
        if raw:
            results[meeting["meeting_name"]] = [FastestLapEntry(**e) for e in raw]
        progress.progress(
            i / len(meetings), text=f"Carregando {meeting['meeting_name']}..."
        )
    progress.empty()
    return results, failures


def main() -> None:
    st.set_page_config(page_title="F1 Fastest Laps", page_icon="🏎️", layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)

    with st.sidebar:
        st.markdown("### Filtros")
        year = st.selectbox("Temporada", options=YEARS, index=YEARS.index(DEFAULT_YEAR))
        session_name = st.selectbox(
            "Sessão",
            options=list(SESSION_LABELS),
            format_func=lambda s: SESSION_LABELS[s],
        )

    st.markdown(
        f"""
        <div class="hero">
          <span class="kicker">OpenF1 &middot; {year} &middot; {SESSION_LABELS[session_name]}</span>
          <h1>F1 &mdash; Voltas Mais Rápidas</h1>
          <p>As 5 voltas mais rápidas de cada Grande Prêmio, quem domina a temporada
          e quão apertada foi cada disputa.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    meetings = fetch_meetings(year)
    if not meetings:
        st.warning(f"Nenhuma etapa encontrada para {year}.")
        return

    results, failures = load_season(meetings, session_name)
    if failures:
        st.caption(f"{failures} etapa(s) não puderam ser carregadas e foram ignoradas.")
    if not results:
        st.info("Sem dados de voltas para esta temporada e sessão.")
        return

    teams = team_top_counts(results)
    drivers = driver_p1_counts(results)
    spreads = spread_per_meeting(results)
    closest = min(spreads, key=lambda s: s.gap) if spreads else None

    # --- KPIs -------------------------------------------------------------
    cols = st.columns(4)
    cards = [
        kpi(
            "Etapas analisadas",
            str(len(results)),
            f"de {len(meetings)} no calendário",
            NEON_VIOLET,
        ),
        kpi(
            "Mais voltas P1",
            drivers[0].label if drivers else "-",
            f"{drivers[0].detail} · {drivers[0].count} GP(s)" if drivers else "",
            NEON_PINK,
            team_hex(drivers[0].colour) if drivers else None,
        ),
        kpi(
            "Equipe dominante",
            str(teams[0].count) if teams else "-",
            f"{teams[0].label} · aparições no Top 5" if teams else "",
            NEON_ORANGE,
            team_hex(teams[0].colour) if teams else None,
        ),
        kpi(
            "Disputa mais apertada",
            f"{closest.gap:.3f} s" if closest else "-",
            f"P1 → P5 em {closest.meeting_name}" if closest else "",
            NEON_CYAN,
        ),
    ]
    for col, card in zip(cols, cards, strict=True):
        col.markdown(card, unsafe_allow_html=True)

    # --- Temporada --------------------------------------------------------
    section("Quem domina a temporada", "Somando o Top 5 de voltas de todos os GPs")
    chart_h = max(260, 34 * max(len(teams), len(drivers)) + 70)
    left, right = st.columns(2, gap="medium")
    with left:
        st.markdown("**Aparições no Top 5 por equipe**")
        st.plotly_chart(
            count_bar_chart(teams, "aparições", "Aparições", chart_h),
            width="stretch",
            config={"displayModeBar": False},
        )
    with right:
        st.markdown("**Voltas mais rápidas (P1) por piloto**")
        st.plotly_chart(
            count_bar_chart(drivers, "GPs com a volta mais rápida", "P1", chart_h),
            width="stretch",
            config={"displayModeBar": False},
        )

    section(
        "Quão apertada foi cada disputa",
        "Diferença entre a 1ª e a 5ª volta mais rápida de cada GP — quanto menor, mais equilibrado",
    )
    st.plotly_chart(
        spread_chart(spreads),
        width="stretch",
        config={"displayModeBar": False},
    )

    # --- Detalhe do GP ----------------------------------------------------
    section("Detalhe do Grande Prêmio")
    meeting_by_name = {m["meeting_name"]: m for m in meetings}
    gp = st.selectbox("Escolha o GP", options=list(results))
    meeting = meeting_by_name[gp]
    st.caption(f"{meeting['circuit_short_name']}, {meeting['country_name']}")

    entries = results[gp]
    df = pd.DataFrame([e.model_dump() for e in entries])
    df["gap"] = gaps_to_leader(entries)
    df["time"] = df["lap_duration"].apply(format_lap_time)
    df["colour"] = df["team_colour"].apply(team_hex)

    board_col, chart_col = st.columns([1, 1], gap="medium")
    with board_col:
        st.markdown(leaderboard(df), unsafe_allow_html=True)
    with chart_col:
        st.plotly_chart(
            gap_chart(df), width="stretch", config={"displayModeBar": False}
        )

    with st.expander("Ver dados em tabela"):
        st.dataframe(
            df[
                ["rank", "driver_name", "team_name", "lap_number", "time", "gap"]
            ].rename(
                columns={
                    "rank": "Pos",
                    "driver_name": "Piloto",
                    "team_name": "Equipe",
                    "lap_number": "Volta",
                    "time": "Tempo",
                    "gap": "Dif. P1 (s)",
                }
            ),
            width="stretch",
            hide_index=True,
        )


if __name__ == "__main__":
    main()
