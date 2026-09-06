import pandas as pd
import plotly.colors
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

DATA_PATH = "nba_team_fit_sheets.xlsx"

TEAM_COLORS = {
    "ATL": "#E03A3E", "BOS": "#007A33", "BKN": "#000000", "CHA": "#1D1160", "CHI": "#CE1141",
    "CLE": "#860038", "DAL": "#00538C", "DEN": "#0E2240", "DET": "#C8102E", "GSW": "#1D428A",
    "HOU": "#CE1141", "IND": "#002D62", "LAC": "#C8102E", "LAL": "#552583", "MEM": "#5D76A9",
    "MIA": "#98002E", "MIL": "#00471B", "MIN": "#0C2340", "NOP": "#0C2340", "NYK": "#006BB6",
    "OKC": "#007AC1", "ORL": "#0077C0", "PHI": "#006BB6", "PHX": "#1D1160", "POR": "#E03A3E",
    "SAC": "#5A2D81", "SAS": "#C4CED4", "TOR": "#CE1141", "UTA": "#002B5C", "WAS": "#002B5C",
}

NEED_CATEGORIES = [
    "SCORING EFFICIENCY", "3 POINT SHOOTING", "ISOLATION SCORING", "ON BALL DEFENSE",
    "PAINT DEFENSE", "PLAYMAKING", "POSSESSIONS", "REBOUNDING",
]
ALL_CATEGORIES = NEED_CATEGORIES + ["RIM PRESSURE", "DEFENSIVE EPM"]


def table_height(n_rows, max_height=600):
    # Sized to fit exactly n_rows + the header, capped at max_height -- st.dataframe leaves
    # trailing blank space (reads as an empty row) if a fixed height is taller than the content.
    return min(max_height, (n_rows + 1) * 35 + 3)


st.set_page_config(page_title="NBA Player Value Model", layout="wide", page_icon="🏀")


@st.cache_data
def load_data():
    rankings = pd.read_excel(DATA_PATH, sheet_name="Rankings")
    rankings_playoffs = pd.read_excel(DATA_PATH, sheet_name="Rankings Playoffs")
    team_needs = pd.read_excel(DATA_PATH, sheet_name="Team Needs").set_index("TEAM_ABBREVIATION")
    team_sheets = {
        team: pd.read_excel(DATA_PATH, sheet_name=team) for team in team_needs.index
    }
    fit_matrix = pd.read_excel(DATA_PATH, sheet_name="Fit Matrix").set_index("PLAYER_NAME")
    return rankings, rankings_playoffs, team_needs, team_sheets, fit_matrix


def percentile_color(pct):
    # Same RdYlGn scale used elsewhere in the app (scatter plot, fit-sheet bar charts) -- red at
    # the 0th percentile, green at the 100th, so this reads consistently with everything else.
    return plotly.colors.sample_colorscale("RdYlGn", pct / 100)[0]


def render_fit_legend():
    n_stops = 20
    stops = plotly.colors.sample_colorscale("RdYlGn", [i / (n_stops - 1) for i in range(n_stops)])
    gradient = ", ".join(stops)
    st.markdown(
        f'<div style="background: linear-gradient(to right, {gradient}); '
        f'height: 16px; border-radius: 4px; margin-top: 4px;"></div>'
        f'<div style="display:flex; justify-content:space-between; font-size:12px; color:gray;">'
        f'<span>0th percentile (worst fit)</span><span>100th percentile (best fit)</span></div>',
        unsafe_allow_html=True,
    )


rankings, rankings_playoffs, team_needs, team_sheets, fit_matrix = load_data()

st.title("🏀 NBA Player Value Model")
st.caption(
    "A weighted, position-relative worth score for every rotation player this season, calibrated "
    "into a theoretical projected salary, plus team-by-team need profiles and recommended fits."
)

page = st.sidebar.radio(
    "View",
    ["League Rankings", "Team Explorer", "Category Rankings", "Best Value Contracts", "Worst Value Contracts"],
)

if page == "League Rankings":
    st.header("League Rankings")

    season_mode = st.radio(
        "Season", ["Regular Season", "Playoffs"], horizontal=True,
        help="Playoffs mode scores players only against other 2026 playoff participants, using "
             "2026 playoff stats instead of the regular season. Defensive EPM is excluded (no "
             "playoff-specific data source), and PROJECTED_SALARY uses its own curve fit "
             "specifically calibrated to the playoff population.",
    )
    active_rankings = rankings if season_mode == "Regular Season" else rankings_playoffs
    if season_mode == "Playoffs":
        st.caption(
            f"{len(rankings_playoffs)} players who logged 40+ total minutes across the 2026 "
            "playoffs. Defensive EPM excluded from WORTH_SCORE; PROJECTED_SALARY uses a separate "
            "curve fit on playoff data."
        )

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Players Scored", len(active_rankings))
    col2.metric("Median Salary", f"${active_rankings['SALARY'].median():,.0f}")
    col3.metric("Biggest Surplus", active_rankings.loc[active_rankings["SURPLUS"].idxmax(), "PLAYER_NAME"])
    col4.metric("Biggest Overpay", active_rankings.loc[active_rankings["SURPLUS"].idxmin(), "PLAYER_NAME"])

    st.subheader("Filters")
    fcol1, fcol2, fcol3 = st.columns(3)
    teams = sorted(active_rankings["TEAM_ABBREVIATION"].dropna().unique())
    POSITION_ORDER = ["Guard", "Forward", "Guard-Forward", "Center"]
    present_positions = set(active_rankings["POSITION_GROUP"].dropna().unique())
    positions = [p for p in POSITION_ORDER if p in present_positions]
    team_filter = fcol1.multiselect("Team", teams)
    pos_filter = fcol2.multiselect("Position", positions)
    name_filter = fcol3.text_input("Search player")

    filtered = active_rankings.copy()
    if team_filter:
        filtered = filtered[filtered["TEAM_ABBREVIATION"].isin(team_filter)]
    if pos_filter:
        filtered = filtered[filtered["POSITION_GROUP"].isin(pos_filter)]
    if name_filter:
        filtered = filtered[filtered["PLAYER_NAME"].str.contains(name_filter, case=False, na=False)]

    st.subheader("Actual vs. Projected Salary")
    scatter_df = filtered.dropna(subset=["SALARY", "PROJECTED_SALARY"])
    fig = px.scatter(
        scatter_df, x="SALARY", y="PROJECTED_SALARY", color="SURPLUS",
        color_continuous_scale="RdYlGn", hover_name="PLAYER_NAME",
        hover_data={"WORTH_SCORE": ":.2f", "SALARY": ":$,.0f", "PROJECTED_SALARY": ":$,.0f", "SURPLUS": False},
        labels={"SALARY": "Actual Salary", "PROJECTED_SALARY": "Model-Projected Salary"},
    )
    max_val = max(scatter_df["SALARY"].max(), scatter_df["PROJECTED_SALARY"].max())
    fig.add_trace(go.Scatter(x=[0, max_val], y=[0, max_val], mode="lines", line=dict(dash="dash", color="gray"), name="Fair Value", showlegend=True))
    fig.update_layout(height=520)
    st.plotly_chart(fig, width="stretch")

    st.subheader("Player Table")
    display_cols = ["RANK", "PLAYER_NAME", "TEAM_ABBREVIATION", "POSITION_GROUP", "SALARY", "PROJECTED_SALARY", "SURPLUS", "WORTH_SCORE"] + NEED_CATEGORIES + ["RIM PRESSURE", "DEFENSIVE EPM"]
    display_cols = [c for c in display_cols if c in filtered.columns]
    st.dataframe(
        filtered[display_cols].sort_values("WORTH_SCORE", ascending=False).round(2),
        width="stretch", height=table_height(len(filtered)), hide_index=True,
        column_config={
            "PLAYER_NAME": "Player",
            "TEAM_ABBREVIATION": "Team",
            "POSITION_GROUP": "Position",
            "WORTH_SCORE": "Worth Score",
            "SALARY": st.column_config.NumberColumn(format="$%,d"),
            "PROJECTED_SALARY": st.column_config.NumberColumn(label="Projected Salary", format="$%,d"),
            "SURPLUS": st.column_config.NumberColumn(format="$%,d"),
        },
    )

elif page == "Team Explorer":
    st.header("Team Explorer")
    team_abbr = st.selectbox("Select a team", sorted(team_needs.index))
    color = TEAM_COLORS.get(team_abbr, "#1D428A")

    needs_row = team_needs.loc[team_abbr].sort_values(ascending=False)
    sheet = team_sheets[team_abbr]

    left, right = st.columns([1, 2])

    with left:
        st.subheader(f"{team_abbr} Needs")
        active_needs = needs_row[needs_row > 0]
        if len(active_needs):
            st.caption("Top need: **" + active_needs.index[0] + "**")
        else:
            st.caption("No categories below league average.")
        needs_fig = go.Figure(go.Bar(
            x=needs_row.values, y=needs_row.index, orientation="h",
            marker_color=color,
        ))
        needs_fig.update_layout(
            xaxis_title="Weighted Need Score", height=420,
            yaxis=dict(autorange="reversed"), margin=dict(l=10, r=10, t=10, b=10),
        )
        st.plotly_chart(needs_fig, width="stretch")

    with right:
        header_col, toggle_col = st.columns([2, 1])
        header_col.subheader(f"Recommended Fits for {team_abbr}")
        sort_choice = toggle_col.radio(
            "Sort by", ["Fit", "Overall", "Value"], horizontal=True, label_visibility="collapsed",
        )
        sort_col = {"Fit": "FIT_SCORE", "Overall": "COMBINED_SCORE", "Value": "SURPLUS"}[sort_choice]
        sheet_sorted = sheet.sort_values(sort_col, ascending=False).reset_index(drop=True)
        sheet_sorted.insert(0, "RANK", sheet_sorted.index + 1)

        show_cols = ["RANK", "PLAYER_NAME", "FIT_SCORE", "COMBINED_SCORE", "SALARY", "PROJECTED_SALARY", "SURPLUS", "WORTH_SCORE"]
        show_cols = [c for c in show_cols if c in sheet_sorted.columns]
        st.dataframe(
            sheet_sorted[show_cols].round(2),
            width="stretch", height=table_height(len(sheet_sorted)), hide_index=True,
            column_config={
                "PLAYER_NAME": "Player",
                "WORTH_SCORE": "Worth Score",
                "SALARY": st.column_config.NumberColumn(format="$%,d"),
                "PROJECTED_SALARY": st.column_config.NumberColumn(label="Projected Salary", format="$%,d"),
                "SURPLUS": st.column_config.NumberColumn(format="$%,d"),
            },
        )

    st.subheader("Fit Sheet Snapshot")
    bar_fig = px.bar(
        sheet_sorted.sort_values(sort_col, ascending=True),
        x=sort_col, y="PLAYER_NAME", orientation="h",
        color="SURPLUS", color_continuous_scale="RdYlGn",
        hover_data={"SALARY": ":$,.0f", "PROJECTED_SALARY": ":$,.0f", "WORTH_SCORE": ":.2f"},
    )
    sort_col_labels = {"FIT_SCORE": "Fit Score", "COMBINED_SCORE": "Overall Score", "SURPLUS": "Surplus (Value)"}
    bar_fig.update_layout(
        height=420, margin=dict(l=10, r=10, t=10, b=10),
        xaxis_title=sort_col_labels[sort_col], yaxis_title="Player",
    )
    st.plotly_chart(bar_fig, width="stretch")

    st.subheader("Search Any Player's Fit")
    st.caption(f"Not just the top 10 -- look up any player's fit score against {team_abbr} specifically.")
    all_players = sorted(rankings["PLAYER_NAME"].dropna().unique())
    searched_player = st.selectbox(
        "Search for a player", all_players, index=None, placeholder="Type a player name...",
        key="player_fit_search",
    )
    if searched_player:
        player_team = rankings.loc[rankings["PLAYER_NAME"] == searched_player, "TEAM_ABBREVIATION"]
        score = fit_matrix.loc[searched_player, team_abbr] if searched_player in fit_matrix.index else None
        if len(player_team) and player_team.values[0] == team_abbr:
            st.info(f"**{searched_player}** is already on the {team_abbr} roster.")
        elif score is None or pd.isna(score):
            st.warning(
                f"**{searched_player}** isn't eligible for fit scoring against {team_abbr} "
                "(either a top-tier/excluded player, or no matched 2025-26 salary)."
            )
        else:
            team_col = fit_matrix[team_abbr].dropna()
            pct = (team_col.rank(pct=True) * 100).loc[searched_player]
            color = percentile_color(pct)
            st.markdown(
                f'<div style="background-color:{color}; padding: 18px; border-radius: 10px; '
                f'text-align:center; margin-top:8px;">'
                f'<span style="font-size:26px; font-weight:bold; color:black;">{score:.2f}</span><br>'
                f'<span style="color:black;">Fit Score for {team_abbr} '
                f'&mdash; {pct:.0f}th percentile among all eligible players</span></div>',
                unsafe_allow_html=True,
            )
            render_fit_legend()

elif page == "Category Rankings":
    st.header("Category Rankings")
    category = st.selectbox("Category", ALL_CATEGORIES)

    cat_ranked = rankings.dropna(subset=[category]).sort_values(category, ascending=False).head(10)
    cat_ranked = cat_ranked.reset_index(drop=True)
    cat_ranked = cat_ranked.drop(columns="RANK")
    cat_ranked.insert(0, "RANK", cat_ranked.index + 1)

    show_cols = ["RANK", "PLAYER_NAME", "TEAM_ABBREVIATION", "POSITION_GROUP", category, "SALARY", "WORTH_SCORE"]
    show_cols = [c for c in show_cols if c in cat_ranked.columns]
    st.dataframe(
        cat_ranked[show_cols].round(2),
        width="stretch", height=table_height(len(cat_ranked)), hide_index=True,
        column_config={
            "PLAYER_NAME": "Player",
            "TEAM_ABBREVIATION": "Team",
            "POSITION_GROUP": "Position",
            "WORTH_SCORE": "Worth Score",
            "SALARY": st.column_config.NumberColumn(format="$%,d"),
        },
    )

    bar_fig = px.bar(
        cat_ranked.sort_values(category, ascending=False),
        x=category, y="PLAYER_NAME", orientation="h",
        color=category, color_continuous_scale="Blues",
        hover_data={"SALARY": ":$,.0f", "WORTH_SCORE": ":.2f"},
    )
    bar_fig.update_coloraxes(showscale=False)
    bar_fig.update_layout(
        height=420, margin=dict(l=10, r=10, t=10, b=10),
        xaxis_title=f"{category.title()} (z-score)", yaxis_title="Player",
        yaxis=dict(autorange="reversed"),
    )
    st.plotly_chart(bar_fig, width="stretch")

else:
    is_best = page == "Best Value Contracts"
    st.header(page)
    st.caption(
        "Players the model values well above their actual salary (PROJECTED_SALARY - SALARY)."
        if is_best else
        "Players the model values well below their actual salary (PROJECTED_SALARY - SALARY)."
    )

    # Rookie-scale contracts (drafted 2022-2025, still in their 4-year rookie deal) are set by draft
    # slot, not the market -- they show up as huge "surplus" purely because a great young player on a
    # cheap rookie deal isn't actually a market inefficiency the way an underpaid veteran is. Default
    # to excluding them on Best Value specifically, since that's where the effect shows up (a rookie
    # deal can't be a bad contract for Worst Value the same way).
    exclude_rookies = st.checkbox(
        "Exclude rookie-scale contracts", value=is_best,
        help="Rookie-scale deals (2022-2025 draft classes) are set by draft slot, not the market, "
             "so a great young player on a cheap rookie deal isn't a real market inefficiency.",
    )

    priced = rankings.dropna(subset=["SALARY", "PROJECTED_SALARY"])
    if exclude_rookies and "ROOKIE_SCALE" in priced.columns:
        priced = priced[~priced["ROOKIE_SCALE"]]
    top20 = priced.sort_values("SURPLUS", ascending=not is_best).head(20).reset_index(drop=True)
    top20 = top20.drop(columns="RANK")
    top20.insert(0, "RANK", top20.index + 1)

    show_cols = ["RANK", "PLAYER_NAME", "TEAM_ABBREVIATION", "POSITION_GROUP", "SALARY", "PROJECTED_SALARY", "SURPLUS", "WORTH_SCORE"]
    show_cols = [c for c in show_cols if c in top20.columns]
    st.dataframe(
        top20[show_cols].round(2),
        width="stretch", height=table_height(len(top20)), hide_index=True,
        column_config={
            "PLAYER_NAME": "Player",
            "TEAM_ABBREVIATION": "Team",
            "POSITION_GROUP": "Position",
            "WORTH_SCORE": "Worth Score",
            "SALARY": st.column_config.NumberColumn(format="$%,d"),
            "PROJECTED_SALARY": st.column_config.NumberColumn(label="Projected Salary", format="$%,d"),
            "SURPLUS": st.column_config.NumberColumn(format="$%,d"),
        },
    )

    # Sorted so rank 1 (biggest surplus for Best, biggest overpay for Worst) is the first row --
    # combined with the reversed y-axis below, that puts rank 1 at the top of the chart either way.
    chart_df = top20.sort_values("SURPLUS", ascending=not is_best).copy()
    chart_df["SURPLUS_MAGNITUDE"] = chart_df["SURPLUS"].abs()
    bar_fig = px.bar(
        chart_df,
        x="SURPLUS", y="PLAYER_NAME", orientation="h",
        color="SURPLUS_MAGNITUDE",
        color_continuous_scale="Greens" if is_best else "Reds",
        hover_data={"SALARY": ":$,.0f", "PROJECTED_SALARY": ":$,.0f", "WORTH_SCORE": ":.2f", "SURPLUS_MAGNITUDE": False},
    )
    bar_fig.update_coloraxes(showscale=False)
    bar_fig.update_layout(
        height=420, margin=dict(l=10, r=10, t=10, b=10),
        xaxis_title="Surplus (Projected - Actual Salary)", yaxis_title="Player",
        yaxis=dict(autorange="reversed"),
    )
    st.plotly_chart(bar_fig, width="stretch")
