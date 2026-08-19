import pandas as pd
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
    team_needs = pd.read_excel(DATA_PATH, sheet_name="Team Needs").set_index("TEAM_ABBREVIATION")
    team_sheets = {
        team: pd.read_excel(DATA_PATH, sheet_name=team) for team in team_needs.index
    }
    return rankings, team_needs, team_sheets


rankings, team_needs, team_sheets = load_data()

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

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Players Scored", len(rankings))
    col2.metric("Median Salary", f"${rankings['SALARY'].median():,.0f}")
    col3.metric("Biggest Surplus", rankings.loc[rankings["SURPLUS"].idxmax(), "PLAYER_NAME"])
    col4.metric("Biggest Overpay", rankings.loc[rankings["SURPLUS"].idxmin(), "PLAYER_NAME"])

    st.subheader("Filters")
    fcol1, fcol2, fcol3 = st.columns(3)
    teams = sorted(rankings["TEAM_ABBREVIATION"].dropna().unique())
    POSITION_ORDER = ["Guard", "Forward", "Guard-Forward", "Center"]
    present_positions = set(rankings["POSITION_GROUP"].dropna().unique())
    positions = [p for p in POSITION_ORDER if p in present_positions]
    team_filter = fcol1.multiselect("Team", teams)
    pos_filter = fcol2.multiselect("Position", positions)
    name_filter = fcol3.text_input("Search player")

    filtered = rankings.copy()
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

    priced = rankings.dropna(subset=["SALARY", "PROJECTED_SALARY"])
    top10 = priced.sort_values("SURPLUS", ascending=not is_best).head(10).reset_index(drop=True)
    top10 = top10.drop(columns="RANK")
    top10.insert(0, "RANK", top10.index + 1)

    show_cols = ["RANK", "PLAYER_NAME", "TEAM_ABBREVIATION", "POSITION_GROUP", "SALARY", "PROJECTED_SALARY", "SURPLUS", "WORTH_SCORE"]
    show_cols = [c for c in show_cols if c in top10.columns]
    st.dataframe(
        top10[show_cols].round(2),
        width="stretch", height=table_height(len(top10)), hide_index=True,
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
    chart_df = top10.sort_values("SURPLUS", ascending=not is_best).copy()
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
