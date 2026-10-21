"""IPL MELIon - interactive dashboard for the IPL 2008-2016 dataset.

Run with:  streamlit run app.py
"""
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

DATA_DIR = Path(__file__).parent

# Dismissals that are not credited to the bowler
NON_BOWLER_DISMISSALS = {"run out", "retired hurt", "obstructing the field"}

st.set_page_config(page_title="IPL MELIon", page_icon="🏏", layout="wide")


@st.cache_data
def load_data():
    ball = pd.read_csv(DATA_DIR / "Ball_by_Ball.csv")
    player = pd.read_csv(DATA_DIR / "Player.csv").drop(columns=["Unnamed: 7"], errors="ignore")
    match = pd.read_csv(DATA_DIR / "Match.csv")
    player_match = pd.read_csv(DATA_DIR / "Player_Match.csv")
    season = pd.read_csv(DATA_DIR / "Season.csv")
    team = pd.read_csv(DATA_DIR / "Team.csv")

    # Blank cells in the ball-by-ball file are stored as a single space
    ball["Batsman_Scored"] = (
        pd.to_numeric(ball["Batsman_Scored"].replace({" ": "0", "Do_nothing": "0"})).astype(int)
    )
    ball["Extra_Runs"] = pd.to_numeric(ball["Extra_Runs"].replace(" ", "0")).astype(int)
    ball["Total_Runs"] = ball["Batsman_Scored"] + ball["Extra_Runs"]
    ball["Dissimal_Type"] = ball["Dissimal_Type"].str.strip()
    ball["Extra_Type"] = ball["Extra_Type"].str.strip()
    ball["Fielder_Id"] = pd.to_numeric(ball["Fielder_Id"], errors="coerce")

    match["Match_Date"] = pd.to_datetime(match["Match_Date"], format="%d-%b-%y")
    match = match.merge(season[["Season_Id", "Season_Year"]], on="Season_Id")
    ball = ball.merge(match[["Match_Id", "Season_Year"]], on="Match_Id")

    return ball, player, match, player_match, season, team


ball, player, match, player_match, season, team = load_data()

player_names = player.set_index("Player_Id")["Player_Name"]
team_names = team.set_index("Team_Id")["Team_Name"]
team_codes = team.set_index("Team_Id")["Team_Short_Code"]


def with_names(df, id_col, mapping=player_names, name_col="Player"):
    df = df.copy()
    df.insert(0, name_col, df[id_col].map(mapping))
    return df.drop(columns=id_col)


def bar(df, x, y, title, color=None, **kwargs):
    fig = px.bar(df, x=x, y=y, title=title, color=color or y, text_auto=True,
                 color_continuous_scale="Viridis", **kwargs)
    fig.update_layout(xaxis_tickangle=-45, coloraxis_showscale=False, margin=dict(t=50))
    st.plotly_chart(fig, width="stretch")


# ---------------------------------------------------------------- sidebar
st.sidebar.image(str(DATA_DIR / "ipl.jpg"), width="stretch")
st.sidebar.title("IPL MELIon")
seasons = sorted(match["Season_Year"].unique())
year_range = st.sidebar.select_slider("Seasons", options=seasons, value=(seasons[0], seasons[-1]))
top_n = st.sidebar.slider("Top N", 5, 30, 10)
page = st.sidebar.radio(
    "Analysis",
    ["Overview", "Batting", "Bowling", "Fielding", "Teams", "Toss & Results", "Venues & Umpires",
     "Season Awards", "Player Explorer"],
)
st.sidebar.caption("Author - Rohan Malyadri")

in_range = lambda df: df[df["Season_Year"].between(*year_range)]
b = in_range(ball)
m = in_range(match)
pm = player_match[player_match["Match_Id"].isin(m["Match_Id"])]
bowler_wickets = b[b["Dissimal_Type"].ne("") & ~b["Dissimal_Type"].isin(NON_BOWLER_DISMISSALS)]
innings = b.groupby(["Match_Id", "Innings_Id", "Striker_Id"])["Batsman_Scored"].sum().reset_index()

st.title(f"🏏 {page}")
st.caption(f"IPL seasons {year_range[0]} – {year_range[1]}")

# ---------------------------------------------------------------- pages
if page == "Overview":
    c = st.columns(5)
    c[0].metric("Matches", f"{m['Match_Id'].nunique():,}")
    c[1].metric("Runs", f"{b['Total_Runs'].sum():,}")
    c[2].metric("Wickets", f"{b['Dissimal_Type'].ne('').sum():,}")
    c[3].metric("Sixes", f"{(b['Batsman_Scored'] == 6).sum():,}")
    c[4].metric("Fours", f"{(b['Batsman_Scored'] == 4).sum():,}")

    left, right = st.columns(2)
    with left:
        per_season = m.groupby("Season_Year")["Match_Id"].count().reset_index(name="Matches")
        bar(per_season, "Season_Year", "Matches", "Matches per season")
    with right:
        runs_season = b.groupby("Season_Year").agg(
            Runs=("Total_Runs", "sum"), Sixes=("Batsman_Scored", lambda s: (s == 6).sum()),
            Fours=("Batsman_Scored", lambda s: (s == 4).sum())).reset_index()
        fig = px.line(runs_season, x="Season_Year", y=["Sixes", "Fours"], markers=True,
                      title="Boundaries per season")
        st.plotly_chart(fig, width="stretch")

    dismissals = b.loc[b["Dissimal_Type"].ne(""), "Dissimal_Type"].value_counts().reset_index()
    dismissals.columns = ["Dismissal", "Count"]
    fig = px.pie(dismissals, names="Dismissal", values="Count", hole=0.4,
                 title="Wicket types and their count")
    st.plotly_chart(fig, width="stretch")

elif page == "Batting":
    runs = b.groupby("Striker_Id").agg(
        Runs=("Batsman_Scored", "sum"), Balls=("Batsman_Scored", "size"),
        Fours=("Batsman_Scored", lambda s: (s == 4).sum()),
        Sixes=("Batsman_Scored", lambda s: (s == 6).sum()),
        Dots=("Batsman_Scored", lambda s: (s == 0).sum())).reset_index()
    runs["Strike_Rate"] = (runs["Runs"] * 100 / runs["Balls"]).round(1)
    runs = with_names(runs, "Striker_Id")

    tabs = st.tabs(["Most runs", "Most sixes", "Most fours", "Fifties & hundreds",
                    "Highest scores", "Most dot balls", "Season-wise runs"])
    with tabs[0]:
        bar(runs.nlargest(top_n, "Runs"), "Player", "Runs", "Highest run scorers")
    with tabs[1]:
        bar(runs.nlargest(top_n, "Sixes"), "Player", "Sixes", "Most sixes")
    with tabs[2]:
        bar(runs.nlargest(top_n, "Fours"), "Player", "Fours", "Most fours")
    with tabs[3]:
        milestones = innings.groupby("Striker_Id")["Batsman_Scored"].agg(
            Fifties=lambda s: s.between(50, 99).sum(), Hundreds=lambda s: (s >= 100).sum()).reset_index()
        milestones = with_names(milestones, "Striker_Id")
        l, r = st.columns(2)
        with l:
            bar(milestones.nlargest(top_n, "Fifties"), "Player", "Fifties", "Most fifties")
        with r:
            bar(milestones[milestones["Hundreds"] > 0].nlargest(top_n, "Hundreds"),
                "Player", "Hundreds", "Most hundreds")
    with tabs[4]:
        top_scores = with_names(innings.nlargest(top_n, "Batsman_Scored"), "Striker_Id")
        top_scores = top_scores.merge(match[["Match_Id", "Match_Date", "Season_Year"]], on="Match_Id")
        top_scores["Label"] = top_scores["Player"] + " (" + top_scores["Season_Year"].astype(str) + ")"
        bar(top_scores, "Label", "Batsman_Scored", "Highest individual scores",
            labels={"Batsman_Scored": "Runs", "Label": ""})
    with tabs[5]:
        bar(runs.nlargest(top_n, "Dots"), "Player", "Dots", "Most dot balls faced")
    with tabs[6]:
        stars = runs.nlargest(5, "Runs")["Player"].tolist()
        chosen = st.multiselect("Players", sorted(runs["Player"].dropna()), default=stars)
        ids = player.loc[player["Player_Name"].isin(chosen), "Player_Id"]
        sw = b[b["Striker_Id"].isin(ids)].groupby(["Season_Year", "Striker_Id"])["Batsman_Scored"].sum()
        sw = with_names(sw.reset_index(name="Runs"), "Striker_Id")
        fig = px.bar(sw, x="Season_Year", y="Runs", color="Player", barmode="group",
                     title="Player performance in each season")
        st.plotly_chart(fig, width="stretch")
    st.subheader("Batting table")
    st.dataframe(runs.sort_values("Runs", ascending=False), width="stretch", hide_index=True)

elif page == "Bowling":
    bowl = b.groupby("Bowler_Id").agg(Balls=("Total_Runs", "size"), Runs=("Total_Runs", "sum")).reset_index()
    wk = bowler_wickets.groupby("Bowler_Id").size().rename("Wickets")
    bowl = bowl.merge(wk, on="Bowler_Id", how="left").fillna({"Wickets": 0})
    bowl["Wickets"] = bowl["Wickets"].astype(int)
    bowl["Economy"] = (bowl["Runs"] * 6 / bowl["Balls"]).round(2)
    bowl = with_names(bowl, "Bowler_Id")

    l, r = st.columns(2)
    with l:
        bar(bowl.nlargest(top_n, "Wickets"), "Player", "Wickets", "Players with most wickets")
    with r:
        bar(bowl.nlargest(top_n, "Runs"), "Player", "Runs", "Most runs conceded")
    min_balls = st.slider("Minimum balls bowled (for economy)", 60, 1500, 600, step=60)
    eco = bowl[bowl["Balls"] >= min_balls].nsmallest(top_n, "Economy")
    bar(eco, "Player", "Economy", "Best economy rates")
    st.dataframe(bowl.sort_values("Wickets", ascending=False), width="stretch", hide_index=True)

elif page == "Fielding":
    caught = b[b["Dissimal_Type"] == "caught"].groupby("Fielder_Id").size().reset_index(name="Catches")
    caught = caught.rename(columns={"Fielder_Id": "Player_Id"})
    keepers = set(pm.loc[pm["Is_Keeper"] == 1, "Player_Id"])
    stumpings = b[b["Dissimal_Type"] == "stumped"].groupby("Fielder_Id").size().reset_index(name="Stumpings")
    stumpings = stumpings.rename(columns={"Fielder_Id": "Player_Id"})
    l, r = st.columns(2)
    with l:
        bar(with_names(caught.nlargest(top_n, "Catches"), "Player_Id"), "Player", "Catches", "Most catches")
    with r:
        kc = caught[caught["Player_Id"].isin(keepers)].merge(stumpings, on="Player_Id", how="outer").fillna(0)
        kc["Dismissals"] = kc["Catches"] + kc["Stumpings"]
        kc = with_names(kc.nlargest(top_n, "Dismissals"), "Player_Id")
        fig = px.bar(kc, x="Player", y=["Catches", "Stumpings"], title="Wicket-keepers: catches & stumpings")
        fig.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig, width="stretch")

elif page == "Teams":
    wins = m["Match_Winner_Id"].value_counts().rename("Wins")
    played = pd.concat([m["Team_Name_Id"], m["Opponent_Team_Id"]]).value_counts().rename("Played")
    standings = pd.concat([played, wins], axis=1).fillna(0).astype(int).rename_axis("Team_Id").reset_index()
    standings["Win_%"] = (standings["Wins"] * 100 / standings["Played"]).round(1)
    standings = with_names(standings, "Team_Id", team_names, "Team").sort_values("Wins", ascending=False)
    bar(standings, "Team", "Wins", "Most successful IPL teams")
    st.dataframe(standings, width="stretch", hide_index=True)

    l, r = st.columns(2)
    with l:
        team_runs = b.groupby("Team_Batting_Id")["Total_Runs"].sum().reset_index(name="Runs")
        bar(with_names(team_runs, "Team_Batting_Id", team_names, "Team").sort_values("Runs", ascending=False),
            "Team", "Runs", "Total runs by team")
    with r:
        totals = b.groupby(["Match_Id", "Innings_Id", "Team_Batting_Id"])["Total_Runs"].sum().reset_index()
        totals["Team"] = totals["Team_Batting_Id"].map(team_codes)
        fig = px.box(totals, x="Team", y="Total_Runs", points="outliers", title="Innings totals by team")
        st.plotly_chart(fig, width="stretch")

    st.subheader("Head to head")
    l, r = st.columns(2)
    t1 = l.selectbox("Team 1", team["Team_Name"], index=2)
    t2 = r.selectbox("Team 2", team["Team_Name"], index=6)
    id1, id2 = team.set_index("Team_Name").loc[[t1, t2], "Team_Id"]
    h2h = m[((m["Team_Name_Id"] == id1) & (m["Opponent_Team_Id"] == id2)) |
            ((m["Team_Name_Id"] == id2) & (m["Opponent_Team_Id"] == id1))]
    if h2h.empty:
        st.info("These teams did not meet in the selected seasons.")
    else:
        res = h2h["Match_Winner_Id"].map(team_names).fillna("No result").value_counts().reset_index()
        res.columns = ["Winner", "Matches"]
        fig = px.pie(res, names="Winner", values="Matches", title=f"{t1} vs {t2} ({len(h2h)} matches)")
        st.plotly_chart(fig, width="stretch")

    st.subheader("Captains")
    caps = pm[pm["Is_Captain"] == 1].merge(m[["Match_Id", "Match_Winner_Id"]], on="Match_Id")
    caps["Won"] = caps["Team_Id"] == caps["Match_Winner_Id"]
    caps = caps.groupby("Player_Id").agg(Matches=("Match_Id", "count"), Wins=("Won", "sum")).reset_index()
    caps["Win_%"] = (caps["Wins"] * 100 / caps["Matches"]).round(1)
    caps = with_names(caps, "Player_Id").sort_values("Wins", ascending=False)
    bar(caps.head(top_n), "Player", "Wins", "Total wins as captain")

    st.subheader("Squads")
    squad_team = st.selectbox("Team", team["Team_Name"])
    squad_ids = pm.loc[pm["Team_Id"] == team.set_index("Team_Name").loc[squad_team, "Team_Id"], "Player_Id"]
    squad = player[player["Player_Id"].isin(squad_ids)][["Player_Name", "Country", "Batting_Hand", "Bowling_Skill"]]
    st.dataframe(squad, width="stretch", hide_index=True)

elif page == "Toss & Results":
    c = st.columns(3)
    decided = m.dropna(subset=["Match_Winner_Id"])
    toss_win_pct = (decided["Toss_Winner_Id"] == decided["Match_Winner_Id"]).mean() * 100
    c[0].metric("Toss winner also won the match", f"{toss_win_pct:.1f}%")
    c[1].metric("Super overs", int(m["IS_Superover"].sum()))
    c[2].metric("Duckworth-Lewis results", int(m["Is_DuckWorthLewis"].sum()))

    l, r = st.columns(2)
    with l:
        td = m.groupby(["Season_Year", "Toss_Decision"]).size().reset_index(name="Matches")
        fig = px.bar(td, x="Season_Year", y="Matches", color="Toss_Decision", barmode="group",
                     title="Toss decision per season")
        st.plotly_chart(fig, width="stretch")
    with r:
        wt = m["Win_Type"].value_counts().reset_index()
        wt.columns = ["Win_Type", "Matches"]
        st.plotly_chart(px.pie(wt, names="Win_Type", values="Matches", title="How matches were won"),
                        width="stretch")

    def describe(df):
        out = df[["Season_Year", "Match_Date", "Team_Name_Id", "Opponent_Team_Id", "Match_Winner_Id",
                  "Win_Type", "Won_By", "Man_Of_The_Match_Id"]].copy()
        for col in ["Team_Name_Id", "Opponent_Team_Id", "Match_Winner_Id"]:
            out[col] = out[col].map(team_codes)
        out["Man_Of_The_Match_Id"] = out["Man_Of_The_Match_Id"].map(player_names)
        out["Match_Date"] = out["Match_Date"].dt.date
        return out.rename(columns={"Team_Name_Id": "Team", "Opponent_Team_Id": "Opponent",
                                   "Match_Winner_Id": "Winner", "Man_Of_The_Match_Id": "Man of the match"})

    st.subheader("Super over matches")
    st.dataframe(describe(m[m["IS_Superover"] == 1]), width="stretch", hide_index=True)
    st.subheader("Duckworth-Lewis matches")
    st.dataframe(describe(m[m["Is_DuckWorthLewis"] == 1]), width="stretch", hide_index=True)
    st.subheader("All matches")
    st.dataframe(describe(m.sort_values("Match_Date")), width="stretch", hide_index=True)

elif page == "Venues & Umpires":
    venues = m.groupby("Venue_Name")["Match_Id"].count().reset_index(name="Matches")
    bar(venues.nlargest(top_n, "Matches"), "Venue_Name", "Matches", "Matches in each stadium",
        labels={"Venue_Name": "Venue"})

    st.subheader("Most successful team at each venue")
    vw = m.dropna(subset=["Match_Winner_Id"]).groupby(["Venue_Name", "Match_Winner_Id"]).size()
    vw = vw.reset_index(name="Wins").sort_values("Wins", ascending=False).drop_duplicates("Venue_Name")
    vw["Team"] = vw["Match_Winner_Id"].map(team_names)
    st.dataframe(vw[["Venue_Name", "Team", "Wins"]], width="stretch", hide_index=True)

    umps = pd.concat([m["First_Umpire_Id"], m["Second_Umpire_Id"]]).value_counts()
    umps = umps.rename_axis("Player_Id").reset_index(name="Matches")
    bar(with_names(umps.head(top_n), "Player_Id", name_col="Umpire"), "Umpire", "Matches",
        "Umpires with most matches")

elif page == "Season Awards":
    finals = match.sort_values("Match_Date").groupby("Season_Id").tail(1)
    awards = season.merge(finals[["Season_Id", "Match_Winner_Id"]], on="Season_Id")
    awards = awards[awards["Season_Year"].between(*year_range)]
    table = pd.DataFrame({
        "Season": awards["Season_Year"],
        "Champion": awards["Match_Winner_Id"].map(team_names),
        "Orange cap": awards["Orange_Cap_Id"].map(player_names),
        "Purple cap": awards["Purple_Cap_Id"].map(player_names),
        "Man of the series": awards["Man_of_the_Series_Id"].map(player_names),
    })
    st.dataframe(table, width="stretch", hide_index=True)

    titles = table["Champion"].value_counts().reset_index()
    titles.columns = ["Team", "Titles"]
    bar(titles, "Team", "Titles", "IPL titles")

    mom = m["Man_Of_The_Match_Id"].value_counts().rename_axis("Player_Id").reset_index(name="Awards")
    bar(with_names(mom.head(top_n), "Player_Id"), "Player", "Awards", "Most man of the match awards")

elif page == "Player Explorer":
    name = st.selectbox("Player", sorted(player.loc[player["Is_Umpire"] == 0, "Player_Name"]),
                        index=None, placeholder="Choose a player")
    if name:
        info = player[player["Player_Name"] == name].iloc[0]
        pid = info["Player_Id"]
        st.write(f"**Country:** {info['Country']} · **Batting:** {info['Batting_Hand']} · "
                 f"**Bowling:** {info['Bowling_Skill']} · **Born:** {info['DOB']}")
        bat = b[b["Striker_Id"] == pid]
        inns = innings[innings["Striker_Id"] == pid]
        bowled = b[b["Bowler_Id"] == pid]
        c = st.columns(6)
        c[0].metric("Matches", pm.loc[pm["Player_Id"] == pid, "Match_Id"].nunique())
        c[1].metric("Runs", int(bat["Batsman_Scored"].sum()))
        c[2].metric("Highest", int(inns["Batsman_Scored"].max()) if len(inns) else 0)
        c[3].metric("Strike rate", f"{bat['Batsman_Scored'].sum() * 100 / max(len(bat), 1):.1f}")
        c[4].metric("Wickets", int((bowler_wickets["Bowler_Id"] == pid).sum()))
        c[5].metric("Catches", int(((b["Dissimal_Type"] == "caught") & (b["Fielder_Id"] == pid)).sum()))
        per = pd.concat([
            bat.groupby("Season_Year")["Batsman_Scored"].sum().rename("Runs"),
            bowler_wickets[bowler_wickets["Bowler_Id"] == pid].groupby("Season_Year").size().rename("Wickets"),
        ], axis=1).fillna(0).reset_index()
        if not per.empty:
            l, r = st.columns(2)
            with l:
                bar(per, "Season_Year", "Runs", "Runs per season")
            with r:
                bar(per, "Season_Year", "Wickets", "Wickets per season")
