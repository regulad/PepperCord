"""What a watched game's thread is sent, and the sports commands' embeds, from ESPN's own responses."""

from datetime import timedelta
from pathlib import Path

import pytest
from aioespn import (
    Event,
    League,
    News,
    Play,
    Scoreboard,
    Sport,
    Standings,
    State,
    Summary,
)
from aioespn.scoreboard import Situation, Status, StatusType
from aioespn.sports import _LeaguesFeed
from aioespn.summary import SummaryHeader
from discord import Embed

from utils.commands import UserFacingError
from utils.sports import (
    Directory,
    game_embed,
    game_message,
    game_updates,
    joined_update,
    join_lines,
    needs_summary,
    news_embed,
    ordinal,
    scoreboard_embed,
    standings_embed,
)
from utils.sports_watch import should_post

FIXTURES = Path(__file__).parent / "fixtures" / "espn"


def scoreboard(name: str) -> Scoreboard:
    return Scoreboard.model_validate_json(
        (FIXTURES / f"scoreboard-{name}.json").read_bytes()
    )


def event(name: str, short_name: str) -> Event:
    return next(e for e in scoreboard(name).events if e.short_name == short_name)


def with_status(
    event: Event, name: str, state: State, completed: bool = False, period: int = 0
) -> Event:
    status = Status(
        period=period,
        type=StatusType(name=name, state=state, completed=completed, description=name),
    )
    competitions = tuple(
        c.model_copy(update={"status": status}) for c in event.competitions
    )
    return event.model_copy(update={"status": status, "competitions": competitions})


def fits(embed: Embed) -> None:
    """Whether Discord would take the embed."""
    assert len(embed) <= 6000
    assert len(embed.fields) <= 25
    assert len(embed.title or "") <= 256
    assert len(embed.description or "") <= 4096
    for field in embed.fields:
        assert 0 < len(field.name or "") <= 256
        assert 0 < len(field.value or "") <= 1024


def directory() -> Directory:
    soccer = _LeaguesFeed.model_validate_json(
        (FIXTURES / "leagues-soccer.json").read_bytes()
    ).leagues
    leagues = {f"soccer/{league.slug}": league for league in soccer}
    leagues["football/nfl"] = League(
        id="28", slug="nfl", name="National Football League", abbreviation="NFL"
    )
    leagues["football/college-football"] = League(
        id="23", slug="college-football", name="NCAA Football", abbreviation="NCAAF"
    )
    leagues["basketball/mens-college-basketball"] = League(
        id="41",
        slug="mens-college-basketball",
        name="NCAA Men's Basketball",
        abbreviation="NCAAM",
    )
    return Directory(leagues)


def test_finds_leagues_by_name_abbreviation_or_key() -> None:
    leagues = directory()
    assert leagues.resolve("nfl") == "football/nfl"
    assert leagues.resolve("  Premier League ") == "soccer/eng.1"
    assert leagues.resolve("English Premier") == "soccer/eng.1"
    assert leagues.resolve("soccer/eng.1") == "soccer/eng.1"
    # A key ESPN's list leaves out still works, as some of rugby's competitions are.
    assert leagues.resolve("rugby/270559") == "rugby/270559"
    with pytest.raises(UserFacingError, match="could be"):
        leagues.resolve("ncaa")
    with pytest.raises(UserFacingError, match="no league"):
        leagues.resolve("quidditch")
    with pytest.raises(UserFacingError, match="isn't a league"):
        leagues.resolve("soccer/../eng.1")
    with pytest.raises(UserFacingError, match="isn't a league"):
        leagues.resolve("cricket/ipl")


def test_suggests_featured_leagues_first() -> None:
    leagues = directory()
    assert leagues.search("")[:2] == ["football/nfl", "football/college-football"]
    assert leagues.search("ncaa") == [
        "football/college-football",
        "basketball/mens-college-basketball",
    ]
    assert leagues.search("football")[0] == "football/nfl"
    assert all(len(leagues.label(key)) <= 100 for key in leagues.leagues)
    assert leagues.label("football/nfl") == "National Football League (NFL) · Football"


def test_basketball_game_under_way() -> None:
    game = event("basketball-nba-development-live", "RAP @ CAP")
    assert needs_summary(Sport.BASKETBALL, game)  # for its technical and flagrant fouls
    updates = game_updates(Sport.BASKETBALL, "nba-development", game)
    # The 1st and 2nd quarters have ended, with their scores from each quarter's line score.
    assert [(u.key, u.title, u.score) for u in updates] == [
        ("start", "Tip-off", "RAP 0 – 0 CAP"),
        ("period:1", "End of the 1st quarter", "RAP 33 – 22 CAP"),
        ("period:2", "Halftime", "RAP 65 – 59 CAP"),
    ]
    joined = joined_update(Sport.BASKETBALL, game)
    assert joined is not None and joined.score == "RAP 74 – 61 CAP"
    # Each update's message text: the score, then when, as ESPN's scoreboard puts it.
    assert [u.line for u in updates] == [
        "RAP 0 – 0 CAP; Tip-off",
        "RAP 33 – 22 CAP; End of 1st",
        "RAP 65 – 59 CAP; Halftime",
    ]
    assert joined.line == "RAP 74 – 61 CAP; 9:49 - 3rd"


def test_basketball_break_between_quarters() -> None:
    game = event("basketball-nba-development-live", "RAP @ CAP")
    at_break = with_status(game, "STATUS_END_PERIOD", State.IN, period=3)
    assert [u.key for u in game_updates(Sport.BASKETBALL, "nba-development", at_break)][
        -1
    ] == "period:3"


def test_soccer_goals_with_running_score() -> None:
    game = event("soccer-concacaf.nations.league-live", "BER @ GDL")
    updates = game_updates(Sport.SOCCER, "concacaf.nations.league", game)
    assert [(u.title.split(":")[0], u.score, u.when) for u in updates] == [
        ("Kick-off", "BER 0 – 0 GDL", None),
        ("Goal", "BER 0 – 1 GDL", "7'"),
        # Without a line score, half-time's score isn't known once the second half has begun: it isn't sent.
        ("Goal", "BER 0 – 2 GDL", "57'"),
        ("Goal", "BER 1 – 2 GDL", "75'"),
    ]
    # Yellow cards aren't sent, and every update's key is its own.
    keys = [u.key for u in updates]
    assert len(keys) == len(set(keys))


def test_soccer_half_time() -> None:
    game = with_status(
        event("soccer-concacaf.nations.league-live", "BER @ GDL"),
        "STATUS_HALFTIME",
        State.IN,
        period=1,
    )
    half_time = [
        u
        for u in game_updates(Sport.SOCCER, "concacaf.nations.league", game)
        if u.key == "period:1"
    ]
    assert [(u.title, u.score) for u in half_time] == [("Half-time", "BER 1 – 2 GDL")]


def test_football_says_where_the_ball_is() -> None:
    game = with_status(
        event("football-nfl", "LAC @ BAL"), "STATUS_IN_PROGRESS", State.IN, period=1
    )
    baltimore = next(
        c for c in game.competitions[0].competitors if c.home_away == "home"
    )
    situation = Situation(
        down_distance_text="1st & 10 at BAL 23", possession=baltimore.id
    )
    live = game.model_copy(
        update={
            "competitions": (
                game.competitions[0].model_copy(update={"situation": situation}),
            )
        }
    )
    [start] = game_updates(Sport.FOOTBALL, "nfl", live)
    assert start.line == "LAC 0 – 0 BAL; Kickoff\nBAL ball, 1st & 10 at BAL 23"
    joined = joined_update(Sport.FOOTBALL, live)
    assert joined is not None and joined.line.endswith("\nBAL ball, 1st & 10 at BAL 23")

    in_the_red_zone = situation.model_copy(update={"is_red_zone": True})
    live = game.model_copy(
        update={
            "competitions": (
                game.competitions[0].model_copy(update={"situation": in_the_red_zone}),
            )
        }
    )
    assert game_updates(Sport.FOOTBALL, "nfl", live)[0].line.endswith(
        "BAL 23 (red zone)"
    )
    # During an extra point ESPN gives the team with the ball but no down: the line is just the score and when.
    extra_point = Situation(possession=baltimore.id, is_red_zone=True)
    live = game.model_copy(
        update={
            "competitions": (
                game.competitions[0].model_copy(update={"situation": extra_point}),
            )
        }
    )
    assert game_updates(Sport.FOOTBALL, "nfl", live)[0].line == "LAC 0 – 0 BAL; Kickoff"
    # Between plays ESPN can give no situation at all.
    assert game_updates(Sport.FOOTBALL, "nfl", game)[0].line == "LAC 0 – 0 BAL; Kickoff"


def test_football_sends_each_possession_once() -> None:
    game = scoreboard("football-nfl-live").events[0]
    summary = Summary.model_validate_json(
        (FIXTURES / "summary-football-nfl-live.json").read_bytes()
    )
    updates = game_updates(Sport.FOOTBALL, "nfl", game, summary)
    # The punts are sent as they end; the touchdown drive is sent as its scoring play, which says how the drive went.
    assert [u.key for u in updates] == [
        "start",
        "drive:4018730651",
        "play:401873065309",
        "drive:4018730653",
    ]
    assert [u.line for u in updates[1:]] == [
        "LAC 0 – 0 BAL; 13:34 - 1st\nBAL: Punt (3 plays, 5 yards, 1:32)\nLAC ball, 1st & 10 at LAC 49",
        "LAC 7 – 0 BAL; 10:39 - 1st\nLAC: Touchdown (6 plays, 63 yards, 2:49)\nLAC ball, 1st & 10 at LAC 49",
        "LAC 7 – 0 BAL; 8:57 - 1st\nBAL: Punt (3 plays, 4 yards, 1:42)\nLAC ball, 1st & 10 at LAC 49",
    ]
    assert updates[1].title == "Punt: Baltimore Ravens"
    # Before its summary is fetched, a game has no plays to send.
    assert [u.key for u in game_updates(Sport.FOOTBALL, "nfl", game)] == ["start"]


def play(data: str) -> Play:
    return Play.model_validate_json(data)


def test_hockey_penalties() -> None:
    game = with_status(
        event("hockey-nhl", "MTL @ NYR"), "STATUS_IN_PROGRESS", State.IN, period=1
    )
    # A penalty from this game's summary, as ESPN served it on 2026-11-17, without its coordinates and headshots.
    tripping = play(
        """{"id": "401892726000003490", "sequenceNumber": "95",
            "type": {"id": "55", "text": "Tripping", "abbreviation": "Tripping", "penaltyMinutes": "2",
                     "penaltyType": "Minor"},
            "text": "Jacob Fowler Tripping against Gabe Perreault served by Cole Caufield",
            "awayScore": 0, "homeScore": 0, "period": {"number": 1, "displayValue": "1st"},
            "clock": {"displayValue": "18:36"}, "scoringPlay": false, "scoreValue": 0, "team": {"id": "10"}}"""
    )
    hit = play(
        """{"id": "401892726000003480", "type": {"id": "503", "text": "Hit", "abbreviation": "hit"},
            "text": "A hit", "awayScore": 0, "homeScore": 0, "period": {"number": 1}, "clock": {"displayValue": "19:01"},
            "scoringPlay": false, "team": {"id": "10"}}"""
    )
    summary = Summary(header=SummaryHeader(id=game.id), plays=(hit, tripping))
    updates = game_updates(Sport.HOCKEY, "nhl", game, summary)
    assert [u.key for u in updates] == ["start", "play:401892726000003490"]
    assert updates[1].title == "Tripping: Montreal Canadiens"
    assert updates[1].line == (
        "MTL 0 – 0 NYR; 18:36 - 1st\nJacob Fowler Tripping against Gabe Perreault served by Cole Caufield (2 min)"
    )


def test_basketball_technical_and_flagrant_fouls() -> None:
    game = event("basketball-nba-development-live", "RAP @ CAP")

    def foul(number: int, kind: str, text: str) -> Play:
        return play(
            f"""{{"id": "40191455900{number}", "type": {{"id": "{number}", "text": "{kind}"}}, "text": "{text}",
                 "awayScore": 70, "homeScore": 60, "period": {{"number": 3}}, "clock": {{"displayValue": "10:00"}},
                 "team": {{"id": "{game.competitions[0].competitors[0].id}"}}}}"""
        )

    plays = (
        foul(1, "Shooting Foul", "A shooting foul"),
        foul(2, "Technical Foul", "Alperen Sengun technical foul"),
        foul(
            3,
            "Defensive 3-Seconds Technical",
            "Jayson Tatum defensive 3-seconds (technical foul)",
        ),
        foul(4, "Free Throw - Technical", "Desmond Bane makes technical free throw"),
        foul(5, "Flagrant Foul Type 1", "Some flagrant foul type 1"),
        foul(6, "Personal Foul", "Someone personal foul, and is ejected"),
    )
    summary = Summary(header=SummaryHeader(id=game.id), plays=plays)
    misconduct = [
        u
        for u in game_updates(Sport.BASKETBALL, "nba-development", game, summary)
        if u.key.startswith("play:")
    ]
    assert [u.key for u in misconduct] == [
        "play:401914559002",
        "play:401914559005",
        "play:401914559006",
    ]
    assert (
        misconduct[0].line
        == "RAP 70 – 60 CAP; 10:00 - 3rd\nAlperen Sengun technical foul"
    )


def test_baseball_scoring_plays_and_final() -> None:
    game = event("baseball-mlb", "MIL @ TB")
    summary = Summary.model_validate_json(
        (FIXTURES / "summary-baseball-mlb.json").read_bytes()
    )
    assert needs_summary(Sport.BASEBALL, game)
    # Without its summary, a baseball game has no scoring plays to send.
    assert [u.key for u in game_updates(Sport.BASEBALL, "mlb", game)] == [
        "start",
        "final",
    ]

    updates = game_updates(Sport.BASEBALL, "mlb", game, summary)
    assert updates[0].key == "start"
    plays = updates[1:-1]
    assert [(u.score, u.when) for u in plays] == [
        ("MIL 1 – 0 TB", "Top 2nd"),
        ("MIL 2 – 0 TB", "Top 5th"),
        ("MIL 3 – 0 TB", "Top 6th"),
        ("MIL 4 – 0 TB", "Top 6th"),
        ("MIL 4 – 1 TB", "Bottom 9th"),
    ]
    assert plays[0].title == "Play Result: Milwaukee Brewers"
    assert plays[0].line == "MIL 1 – 0 TB; Top 2nd"
    assert plays[0].description is not None and "Turang scored" in plays[0].description
    final = updates[-1]
    assert final.key == "final" and final.score == "MIL 4 – 1 TB"
    assert final.line == "MIL 4 – 1 TB; Final"
    assert final.description is not None
    assert final.description.startswith("Milwaukee Brewers win.")
    assert "R H E" in final.description  # the line score, with runs, hits and errors


def test_called_off() -> None:
    game = with_status(
        event("baseball-mlb", "MIL @ TB"), "STATUS_POSTPONED", State.POST
    )
    assert [(u.key, u.title) for u in game_updates(Sport.BASEBALL, "mlb", game)] == [
        ("status:STATUS_POSTPONED", "STATUS_POSTPONED")
    ]


def test_results_of_fights_sessions_and_matches() -> None:
    card = scoreboard("mma-ufc").events[0]
    fights = game_updates(Sport.MMA, "ufc", card)
    assert len(fights) == 3
    assert all(f.key.startswith("result:") for f in fights)
    assert fights[0].description == "Caio Borralho wins by decision in round 3 at 5:00."
    assert fights[0].when == "Middleweight"
    assert fights[0].line == (
        "Caio Borralho vs. Yousri Belgaroui: Caio Borralho wins by decision in round 3 at 5:00."
    )

    weekend = scoreboard("racing-f1").events[0]
    # Practice isn't sent; qualifying and the race are, each with its order.
    sessions = game_updates(Sport.RACING, "f1", weekend)
    assert [s.title for s in sessions] == ["Qualifying results", "Race results"]
    assert sessions[1].description is not None and sessions[1].description.startswith(
        "1. "
    )

    finals = scoreboard("tennis-atp").events[0]
    matches = game_updates(Sport.TENNIS, "atp", finals)
    # Only singles, and only matches that are over.
    assert [m.key for m in matches] == ["result:187505", "result:187506"]
    assert all(m.description and " bt " in m.description for m in matches)


def test_golf() -> None:
    tournament = scoreboard("golf-pga").events[0]
    assert [u.key for u in game_updates(Sport.GOLF, "pga", tournament)] == ["start"]
    joined = joined_update(Sport.GOLF, tournament)
    assert joined is not None and joined.description is not None
    assert joined.description.startswith("1. Chad Ramey -19")
    finished = with_status(tournament, "STATUS_FINAL", State.POST, completed=True)
    final = game_updates(Sport.GOLF, "pga", finished)[-1]
    assert (
        final.key == "final"
        and final.description is not None
        and "Chad Ramey" in final.description
    )


def test_game_message_gives_away_nothing() -> None:
    finished = event("baseball-mlb", "MIL @ TB")
    embed = game_message(finished, None)
    fits(embed)
    text = str(embed.to_dict())
    assert "4 – 1" not in text and "win" not in text
    assert embed.title == finished.name


def test_posts_games_due_within_the_hour() -> None:
    monday = event("football-nfl", "LAC @ BAL")
    assert (
        monday.current_status is not None and monday.current_status.state is State.PRE
    )
    assert not should_post(monday, monday.date - timedelta(hours=2))
    assert should_post(monday, monday.date - timedelta(minutes=59))
    assert should_post(monday, monday.date + timedelta(minutes=5))  # running late
    assert should_post(
        with_status(monday, "STATUS_IN_PROGRESS", State.IN, period=1), monday.date
    )
    finished = event("football-nfl", "WSH @ NYG")
    assert not should_post(finished, finished.date)


@pytest.mark.parametrize(
    ("sport", "slug", "name"),
    [
        (Sport.BASKETBALL, "nba-development", "basketball-nba-development-live"),
        (
            Sport.SOCCER,
            "concacaf.nations.league",
            "soccer-concacaf.nations.league-live",
        ),
        (Sport.BASEBALL, "mlb", "baseball-mlb"),
        (Sport.FOOTBALL, "nfl", "football-nfl"),
        (Sport.GOLF, "pga", "golf-pga"),
        (Sport.MMA, "ufc", "mma-ufc"),
        (Sport.RACING, "f1", "racing-f1"),
        (Sport.TENNIS, "atp", "tennis-atp"),
    ],
)
def test_command_embeds_fit(sport: Sport, slug: str, name: str) -> None:
    board = scoreboard(name)
    league = League(id="1", slug=slug, name="A League")
    fits(scoreboard_embed(sport, board, league, f"{sport}/{slug}"))
    for game in board.events:
        fits(game_embed(sport, slug, game, None, league))
        fits(game_message(game, league))
        for update in game_updates(sport, slug, game):
            fits(update.embed())


def test_scoreboard_lines() -> None:
    board = scoreboard("football-nfl")
    embed = scoreboard_embed(Sport.FOOTBALL, board, None, "football/nfl")
    assert embed.description is not None
    lines = embed.description.splitlines()
    assert lines[0] == "**WSH** 24, NYG 21 · Final"  # the winner in bold
    assert lines[2].startswith("LAC @ BAL · <t:")


def test_standings_and_news() -> None:
    nfl = Standings.model_validate_json(
        (FIXTURES / "standings-football-nfl.json").read_bytes()
    )
    embed = standings_embed(nfl, None, "football/nfl")
    fits(embed)
    assert embed.fields[0].name == "AFC East"
    assert embed.fields[0].value is not None and embed.fields[0].value.startswith("1. ")
    assert "8-1" in embed.fields[0].value

    epl = Standings.model_validate_json(
        (FIXTURES / "standings-soccer-eng.1.json").read_bytes()
    )
    embed = standings_embed(epl, None, "soccer/eng.1")
    fits(embed)
    assert (
        embed.fields[0].value is not None and "27 pts (9-0-1)" in embed.fields[0].value
    )

    f1 = Standings.model_validate_json(
        (FIXTURES / "standings-racing-f1.json").read_bytes()
    )
    embed = standings_embed(f1, None, "racing/f1")
    fits(embed)
    assert [field.name for field in embed.fields] == [
        "Driver Standings",
        "Constructor Standings",
    ]
    assert embed.fields[0].value is not None and "390 pts" in embed.fields[0].value

    news = News.model_validate_json((FIXTURES / "news-football-nfl.json").read_bytes())
    embed = news_embed(news, None, "football/nfl")
    fits(embed)
    assert embed.description is not None and embed.description.count("](https://") == 3


def test_join_lines() -> None:
    assert join_lines(["a", "b"], 100) == "a\nb"
    lines = [f"line {i}" for i in range(100)]
    joined = join_lines(lines, 60)
    assert len(joined) <= 60
    assert joined.endswith("more.")
    kept = joined.splitlines()[:-1]
    assert kept == lines[: len(kept)]
    assert joined.splitlines()[-1] == f"…and {100 - len(kept)} more."


def test_ordinal() -> None:
    assert [ordinal(n) for n in (1, 2, 3, 4, 11, 12, 13, 21, 22, 101, 111)] == [
        "1st",
        "2nd",
        "3rd",
        "4th",
        "11th",
        "12th",
        "13th",
        "21st",
        "22nd",
        "101st",
        "111th",
    ]
