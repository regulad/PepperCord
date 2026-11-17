"""ESPN's leagues and games as PepperCord shows them: finding a league from what someone typed, what a watched game's
thread is sent as the game is played, and the embeds the sports commands send.

Everything here works on aioespn's models and makes no requests: the cog decides what to fetch, and when.
"""

import re
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from aioespn import (
    Competition,
    Competitor,
    Event,
    League,
    News,
    Play,
    Scoreboard,
    Sport,
    Standings,
    State,
    Status,
    Summary,
)
from aioespn.scoreboard import Grouping
from aioespn.standings import StandingsEntry
from discord import Embed
from discord.utils import format_dt

from utils.commands import UserFacingError

ESPN_RED: Final = 0xCC0000
CREDIT: Final = "Data from ESPN"

SPORT_NAMES: Final[Mapping[Sport, str]] = {
    Sport.AUSTRALIAN_FOOTBALL: "Australian football",
    Sport.BASEBALL: "Baseball",
    Sport.BASKETBALL: "Basketball",
    Sport.FIELD_HOCKEY: "Field hockey",
    Sport.FOOTBALL: "Football",
    Sport.GOLF: "Golf",
    Sport.HOCKEY: "Hockey",
    Sport.LACROSSE: "Lacrosse",
    Sport.MMA: "MMA",
    Sport.RACING: "Racing",
    Sport.RUGBY: "Rugby union",
    Sport.RUGBY_LEAGUE: "Rugby league",
    Sport.SOCCER: "Soccer",
    Sport.TENNIS: "Tennis",
    Sport.VOLLEYBALL: "Volleyball",
    Sport.WATER_POLO: "Water polo",
}

FEATURED: Final[tuple[str, ...]] = (
    "football/nfl",
    "basketball/nba",
    "baseball/mlb",
    "hockey/nhl",
    "basketball/wnba",
    "football/college-football",
    "basketball/mens-college-basketball",
    "basketball/womens-college-basketball",
    "soccer/usa.1",
    "soccer/eng.1",
    "soccer/esp.1",
    "soccer/ger.1",
    "soccer/ita.1",
    "soccer/fra.1",
    "soccer/uefa.champions",
    "soccer/fifa.world",
    "golf/pga",
    "golf/lpga",
    "racing/f1",
    "racing/irl",
    "mma/ufc",
    "tennis/atp",
    "tennis/wta",
    "australian-football/afl",
    "football/cfl",
)
"""The leagues suggested before anything is typed, and preferred when a name matches several."""

SUMMARY_SPORTS: Final = frozenset({Sport.FOOTBALL, Sport.HOCKEY, Sport.BASEBALL})
"""Sports whose scoring plays are only in a game's summary."""

DETAIL_SPORTS: Final = frozenset({Sport.SOCCER, Sport.RUGBY, Sport.RUGBY_LEAGUE})
"""Sports whose scoreboards list each goal, try and card."""

RESULT_SPORTS: Final = frozenset({Sport.RACING, Sport.MMA, Sport.TENNIS})
"""Sports whose events hold many competitions, each with its own result: race sessions, fights and tennis matches."""

RUGBY_SCORES: Final = frozenset(
    {"try", "penalty try", "conversion", "penalty goal", "drop goal", "field goal"}
)

HALF_SECONDS: Final[Mapping[Sport, int]] = {
    Sport.SOCCER: 45 * 60,
    Sport.RUGBY: 40 * 60,
    Sport.RUGBY_LEAGUE: 40 * 60,
}
"""How long a half lasts, to tell a first-half goal from a second-half one where ESPN gives only the match clock."""

REGULATION: Final[Mapping[Sport, int]] = {
    Sport.AUSTRALIAN_FOOTBALL: 4,
    Sport.BASEBALL: 9,
    Sport.BASKETBALL: 4,
    Sport.FIELD_HOCKEY: 4,
    Sport.FOOTBALL: 4,
    Sport.HOCKEY: 3,
    Sport.LACROSSE: 4,
    Sport.RUGBY: 2,
    Sport.RUGBY_LEAGUE: 2,
    Sport.SOCCER: 2,
    Sport.VOLLEYBALL: 5,
    Sport.WATER_POLO: 4,
}

START_TITLES: Final[Mapping[Sport, str]] = {
    Sport.BASEBALL: "First pitch",
    Sport.BASKETBALL: "Tip-off",
    Sport.FOOTBALL: "Kickoff",
    Sport.GOLF: "Tee off",
    Sport.HOCKEY: "Puck drop",
    Sport.RUGBY: "Kick-off",
    Sport.RUGBY_LEAGUE: "Kick-off",
    Sport.SOCCER: "Kick-off",
    Sport.VOLLEYBALL: "First serve",
}

BREAKS: Final = frozenset({"STATUS_END_PERIOD", "STATUS_HALFTIME"})
"""Statuses that mean the period in :attr:`Status.period` has just ended."""

_SLUG = re.compile(r"[a-z0-9][a-z0-9._-]*")


def parse_key(key: str) -> tuple[Sport, str]:
    """Split a league's key, such as ``football/nfl``, into its sport and slug. Raises ValueError if it isn't one."""
    sport, _, slug = key.partition("/")
    if not _SLUG.fullmatch(slug):
        raise ValueError(f"not a league: {key!r}")
    return Sport(sport), slug


def ordinal(number: int) -> str:
    if 10 <= number % 100 <= 20:
        return f"{number}th"
    return f"{number}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(number % 10, 'th') }"


def truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def join_lines(lines: Sequence[str], limit: int, more: str = "…and {} more.") -> str:
    """As many of ``lines`` as fit in ``limit`` characters, and how many were left out."""
    kept: list[str] = []
    length = 0
    for index, line in enumerate(lines):
        left = len(lines) - index
        needed = length + len(line) + (1 if kept else 0)
        # Leave room to say how many lines were left out, unless this is the last.
        reserve = len(more.format(left - 1)) + 1 if left > 1 else 0
        if needed + reserve > limit:
            kept.append(more.format(left))
            break
        kept.append(line)
        length = needed
    return truncate("\n".join(kept), limit)


def team_colour(competitor: Competitor | None) -> int | None:
    if competitor is None or competitor.team is None or not competitor.team.color:
        return None
    try:
        return int(competitor.team.color, 16)
    except ValueError:
        return None


class Directory:
    """Every league ESPN lists, by key, such as ``football/nfl``, and finding one from what someone typed."""

    def __init__(self, leagues: Mapping[str, League]) -> None:
        self.leagues = dict(leagues)

    def league(self, key: str) -> League | None:
        return self.leagues.get(key)

    def name(self, key: str) -> str:
        league = self.leagues.get(key)
        return league.name if league is not None else key

    def label(self, key: str) -> str:
        """The league's name, abbreviation and sport, as a choice in Discord shows it."""
        league = self.leagues.get(key)
        sport = SPORT_NAMES.get(Sport(key.partition("/")[0]), "")
        if league is None:
            return truncate(f"{key} · {sport}", 100)
        name = league.name
        if (
            league.abbreviation
            and league.abbreviation.casefold() not in name.casefold()
        ):
            name += f" ({league.abbreviation})"
        return truncate(f"{name} · {sport}", 100)

    def _fields(self, key: str) -> list[str]:
        league = self.leagues[key]
        fields = [
            league.abbreviation,
            league.short_name,
            league.midsize_name,
            league.name,
            league.slug,
            key,
        ]
        return [field.casefold() for field in fields if field]

    def _rank(self, text: str, key: str) -> int | None:
        fields = self._fields(key)
        if text in fields:
            return 0
        if any(field.startswith(text) for field in fields):
            return 1
        sport = SPORT_NAMES[Sport(key.partition("/")[0])].casefold()
        haystack = " ".join([*fields, sport])
        if all(word in haystack for word in text.split()):
            return 2
        return None

    def _order(self, key: str) -> tuple[int, str]:
        featured = FEATURED.index(key) if key in FEATURED else len(FEATURED)
        return featured, self.leagues[key].name

    def search(self, text: str, limit: int = 25) -> list[str]:
        """The keys of the leagues that best match ``text``, best first."""
        text = text.casefold().strip()
        if not text:
            return [key for key in FEATURED if key in self.leagues][:limit]
        ranked = sorted(
            (rank, *self._order(key), key)
            for key in self.leagues
            if (rank := self._rank(text, key)) is not None
        )
        return [key for *_, key in ranked[:limit]]

    def resolve(self, text: str) -> str:
        """The key of the league ``text`` names: a key itself, or a league's name, abbreviation or slug."""
        wanted = text.casefold().strip()
        if "/" in wanted:
            try:
                sport, slug = parse_key(wanted)
            except ValueError:
                raise UserFacingError(
                    f"`{text}` isn't a league. Name one, such as `nfl`, or give its sport and slug, such as "
                    "`soccer/eng.1`."
                )
            return f"{sport.value}/{slug}"

        exact = sorted(
            (key for key in self.leagues if self._rank(wanted, key) == 0),
            key=self._order,
        )
        if len(exact) == 1 or (exact and exact[0] in FEATURED):
            return exact[0]
        matches = exact or self.search(wanted)
        if len(matches) == 1:
            return matches[0]
        if not matches:
            raise UserFacingError(f"ESPN has no league called `{text}`.")
        options = ", ".join(
            f"`{key}` ({self.leagues[key].name})" for key in matches[:5]
        )
        raise UserFacingError(f"Which league? `{text}` could be {options}.")


# What a watched game's thread is sent.


@dataclass(frozen=True)
class GameUpdate:
    """Something that happened in a game, which its thread is sent once."""

    key: str
    """Names the update within its game. Deriving the same update again gives the same key."""
    title: str
    description: str | None = None
    score: str | None = None
    when: str | None = None
    """When in the game it happened, such as "2nd quarter, 4:31" or "24'"."""
    colour: int | None = None

    def embed(self) -> Embed:
        embed = Embed(
            title=truncate(self.title, 256),
            description=(
                truncate(self.description, 4096)
                if self.description is not None
                else None
            ),
            colour=self.colour if self.colour is not None else ESPN_RED,
        )
        if self.score is not None:
            embed.add_field(name="Score", value=truncate(self.score, 1024))
        if self.when is not None:
            embed.set_footer(text=truncate(self.when, 2048))
        return embed


def needs_summary(sport: Sport, event: Event) -> bool:
    """Whether the event's updates need its summary: football's, hockey's and baseball's scoring plays are only there."""
    status = event.current_status
    return (
        sport in SUMMARY_SPORTS and status is not None and status.state is not State.PRE
    )


def _abbreviation(competitor: Competitor) -> str:
    if competitor.team is not None and competitor.team.abbreviation:
        return competitor.team.abbreviation
    return competitor.short_display_name


def _score(competitor: Competitor) -> str:
    return competitor.score or "0"


def _sides(competition: Competition | None) -> tuple[Competitor, Competitor] | None:
    """A two-sided competition's away and home sides."""
    if competition is None:
        return None
    away, home = competition.away, competition.home
    if away is None or home is None:
        if len(competition.competitors) != 2:
            return None
        away, home = competition.competitors[1], competition.competitors[0]
    return away, home


def _line(sides: tuple[Competitor, Competitor], away: object, home: object) -> str:
    return f"{_abbreviation(sides[0])} {away} – {home} {_abbreviation(sides[1])}"


def score_line(competition: Competition | None) -> str | None:
    """The score, away side first, such as "BAL 17 – 24 KC"."""
    sides = _sides(competition)
    if sides is None:
        return None
    return _line(sides, _score(sides[0]), _score(sides[1]))


def _regulation(sport: Sport, league: str, competition: Competition) -> int:
    if (
        competition.format is not None
        and competition.format.regulation is not None
        and competition.format.regulation.periods
    ):
        return competition.format.regulation.periods
    if sport is Sport.BASKETBALL and league == "mens-college-basketball":
        return 2
    return REGULATION.get(sport, 4)


def _unit(sport: Sport, regulation: int) -> str:
    if sport is Sport.HOCKEY:
        return "period"
    if sport is Sport.BASEBALL:
        return "inning"
    if sport is Sport.VOLLEYBALL:
        return "set"
    return "half" if regulation == 2 else "quarter"


def period_name(sport: Sport, regulation: int, number: int) -> str:
    """Such as "3rd quarter", "2nd half" or "overtime"."""
    if number > regulation and sport not in (Sport.BASEBALL, Sport.VOLLEYBALL):
        extra = number - regulation
        overtime = "extra time" if sport in DETAIL_SPORTS else "overtime"
        return overtime if extra == 1 else f"{ordinal(extra)} {overtime}"
    return f"{ordinal(number)} {_unit(sport, regulation)}"


def _when(sport: Sport, regulation: int, play: Play) -> str | None:
    clock = play.clock.display_value if play.clock is not None else None
    number = play.period.number if play.period is not None else None
    if sport is Sport.BASEBALL and play.period is not None and number:
        return f"{play.period.type or ''} {ordinal(number)}".strip()
    if sport in DETAIL_SPORTS or not number:
        return clock
    period = period_name(sport, regulation, number)
    return f"{period[0].upper()}{period[1:]}, {clock}" if clock else period


def _competitor(competition: Competition, team_id: str | None) -> Competitor | None:
    if team_id is None:
        return None
    return next(
        (
            c
            for c in competition.competitors
            if c.id == team_id or (c.team is not None and c.team.id == team_id)
        ),
        None,
    )


def _describe(play: Play) -> str | None:
    """A detail's athletes, for scoreboard details, which have no text of their own."""
    names = [p.athlete.name for p in play.participants if p.athlete.name]
    if not names:
        return None
    text = ", ".join(names)
    if play.own_goal:
        text += " (own goal)"
    elif play.penalty_kick:
        text += " (penalty)"
    return text


def _play_update(
    sport: Sport,
    regulation: int,
    competition: Competition,
    play: Play,
    key: str,
    score: str | None,
) -> GameUpdate:
    sides = _sides(competition)
    team = _competitor(competition, play.team.id if play.team is not None else None)
    kind = play.type.text if play.type is not None and play.type.text else "Score"
    kind = kind[0].upper() + kind[1:]
    if (
        score is None
        and sides is not None
        and play.away_score is not None
        and play.home_score is not None
    ):
        score = _line(sides, play.away_score, play.home_score)
    return GameUpdate(
        key=key,
        title=f"{kind}: {team.display_name}" if team is not None else kind,
        description=play.text or _describe(play),
        score=score,
        when=_when(sport, regulation, play),
        colour=team_colour(team),
    )


def _detail_key(play: Play) -> str:
    # Scoreboards' details have no IDs: what happened, when and to whom names each.
    kind = play.type.id if play.type is not None else None
    clock = play.clock.value if play.clock is not None else None
    team = play.team.id if play.team is not None else None
    athlete = play.participants[0].athlete.id if play.participants else None
    return f"detail:{kind}:{clock}:{team}:{athlete}"


def _plays(
    sport: Sport, league: str, competition: Competition, summary: Summary | None
) -> Iterator[tuple[int, GameUpdate]]:
    """The game's scoring plays, and soccer's and rugby's red cards, each with the period it was in."""
    regulation = _regulation(sport, league, competition)
    if sport in SUMMARY_SPORTS:
        for play in summary.scoring_summary if summary is not None else ():
            if play.id is None:
                continue
            period = play.period.number if play.period is not None else None
            yield period or 0, _play_update(
                sport, regulation, competition, play, f"play:{play.id}", None
            )
    elif sport in DETAIL_SPORTS:
        sides = _sides(competition)
        goals: dict[str, int] = {}
        if sides is not None:
            goals = {c.team.id if c.team else c.id: 0 for c in sides}
        for play in competition.details:
            kind = (play.type.text or "").casefold() if play.type is not None else ""
            if sport is Sport.SOCCER:
                scoring = play.is_scoring and not play.shootout
            else:
                scoring = kind in RUGBY_SCORES
            if not (scoring or play.red_card or kind == "red card"):
                continue
            score = None
            team = play.team.id if play.team is not None else None
            # Soccer's details add up to the score, each goal counting for the team it was scored for.
            if (
                sport is Sport.SOCCER
                and scoring
                and sides
                and team is not None
                and team in goals
            ):
                goals[team] += 1
                ids = [c.team.id if c.team else c.id for c in sides]
                score = _line(sides, goals[ids[0]], goals[ids[1]])
            clock = play.clock.value if play.clock is not None else None
            period = 1 if clock is None or clock < HALF_SECONDS[sport] else 2
            yield period, _play_update(
                sport, regulation, competition, play, _detail_key(play), score
            )


def _period_total(competitor: Competitor, periods: int) -> float | None:
    values = [line.value for line in competitor.linescores[:periods]]
    if len(values) < periods or None in values:
        return None
    return sum(value for value in values if value is not None)


def _sets_won(sides: tuple[Competitor, Competitor], sets: int) -> tuple[int, int]:
    won = [0, 0]
    for away, home in zip(sides[0].linescores[:sets], sides[1].linescores[:sets]):
        if (
            away.value is not None
            and home.value is not None
            and away.value != home.value
        ):
            won[0 if away.value > home.value else 1] += 1
    return won[0], won[1]


def _period_ends(
    sport: Sport, league: str, competition: Competition, status: Status
) -> Iterator[tuple[int, GameUpdate]]:
    """The end of each regulation period that has ended, with the score at its end, where that's known."""
    sides = _sides(competition)
    if sport is Sport.BASEBALL or sides is None:
        return
    regulation = _regulation(sport, league, competition)
    current = status.period or 0
    at_break = status.state is State.IN and status.type.name in BREAKS
    # A finished game's last period ends with the final whistle, which the final update covers.
    ended = current if at_break else current - 1
    halves = sport in DETAIL_SPORTS
    for number in range(1, min(ended, regulation) + 1):
        if halves and number == regulation:
            break  # the end of the second half is full time, or goes to extra time
        description = None
        if sport is Sport.VOLLEYBALL:
            points = [
                (
                    side.linescores[number - 1].value
                    if len(side.linescores) >= number
                    else None
                )
                for side in sides
            ]
            away_points, home_points = points
            if away_points is None or home_points is None:
                continue
            description = f"Set {number}: " + _line(
                sides, int(away_points), int(home_points)
            )
            score = _line(sides, *_sets_won(sides, number))
            title = f"End of the {ordinal(number)} set"
        else:
            away_total = _period_total(sides[0], number)
            home_total = _period_total(sides[1], number)
            if away_total is not None and home_total is not None:
                score = _line(sides, int(away_total), int(home_total))
            elif at_break and number == current:
                score = _line(sides, _score(sides[0]), _score(sides[1]))
            else:
                continue
            if halves:
                title = "Half-time"
            elif regulation % 2 == 0 and number == regulation // 2:
                title = "Halftime"
            elif number == regulation:
                title = "End of regulation"
            else:
                title = f"End of the {period_name(sport, regulation, number)}"
        yield number, GameUpdate(
            key=f"period:{number}", title=title, description=description, score=score
        )


def line_score(competition: Competition | None, sport: Sport) -> str | None:
    """Each side's score in each period, as a table in a code block."""
    sides = _sides(competition)
    if sides is None:
        return None
    periods = max(len(side.linescores) for side in sides)
    if periods == 0 or periods > 15:
        return None
    header = ["", *(str(number) for number in range(1, periods + 1)), "T"]
    rows = []
    for side in sides:
        cells = [_abbreviation(side)]
        for number in range(periods):
            line = side.linescores[number] if number < len(side.linescores) else None
            value = line.display_value if line is not None else None
            if value is None and line is not None and line.value is not None:
                value = f"{line.value:g}"
            cells.append(value or "-")
        cells.append(_score(side))
        if sport is Sport.BASEBALL:
            cells += [str(side.hits or 0), str(side.errors or 0)]
        rows.append(cells)
    if sport is Sport.BASEBALL:
        header[-1] = "R"
        header += ["H", "E"]
    widths = [max(len(row[i]) for row in (header, *rows)) for i in range(len(header))]
    lines = [
        " ".join(
            cell.rjust(width) if i else cell.ljust(width)
            for i, (cell, width) in enumerate(zip(row, widths))
        )
        for row in (header, *rows)
    ]
    return "```\n" + "\n".join(lines) + "\n```"


def _final(sport: Sport, competition: Competition, status: Status) -> GameUpdate:
    sides = _sides(competition)
    winner = next((c for c in competition.competitors if c.winner), None)
    lines = []
    if winner is not None:
        lines.append(f"{winner.display_name} win.")
    elif sides is not None and _score(sides[0]) == _score(sides[1]):
        lines.append("A draw.")
    if sides is not None and None not in (s.shootout_score for s in sides):
        lines.append(
            f"{_line(sides, sides[0].shootout_score, sides[1].shootout_score)} on penalties."
        )
    if (table := line_score(competition, sport)) is not None:
        lines.append(table)
    return GameUpdate(
        key="final",
        title=status.type.detail or "Final",
        description="\n".join(lines) or None,
        score=score_line(competition),
        colour=team_colour(winner),
    )


def leaderboard(competition: Competition | None, count: int) -> list[str]:
    """A golf tournament's or race's leaders, in order."""
    if competition is None:
        return []
    ordered = sorted(
        competition.competitors,
        key=lambda c: c.order if c.order is not None else len(competition.competitors),
    )
    return [
        f"{index}. {c.display_name}" + (f" {c.score}" if c.score else "")
        for index, c in enumerate(ordered[:count], start=1)
    ]


def _matches(event: Event) -> Iterator[tuple[Grouping | None, Competition]]:
    """An event's competitions with their tennis draws: each singles match, or each race session or fight."""
    for competition in event.competitions:
        yield None, competition
    for grouping in event.groupings:
        if grouping.slug is None or grouping.slug.endswith("singles"):
            for competition in grouping.competitions:
                yield grouping, competition


def _method(competition: Competition) -> str | None:
    # A fight's details include, say, "Unofficial Winner Submission" once it's over.
    for play in competition.details:
        text = play.type.text if play.type is not None else None
        if text and text.startswith("Unofficial Winner "):
            return text.removeprefix("Unofficial Winner ")
    return None


def _result(
    sport: Sport, grouping: Grouping | None, competition: Competition
) -> GameUpdate | None:
    status = competition.status
    if status is None or status.state is not State.POST:
        return None
    key = f"result:{competition.id}"
    kind = competition.type
    if sport is Sport.RACING:
        session = (kind.text or kind.abbreviation) if kind is not None else None
        if session and session.casefold().startswith(("fp", "practice")):
            return None
        if session and session.casefold() == "qual":
            session = "Qualifying"
        return GameUpdate(
            key=key,
            title=f"{session or 'Session'} results",
            description="\n".join(leaderboard(competition, 10)) or None,
        )
    sides = _sides(competition)
    if sides is None:
        return None
    winner = next((c for c in sides if c.winner), None)
    if sport is Sport.MMA:
        # Fighters have no home and away: name them in ESPN's order.
        first, second = competition.competitors[:2]
        names = f"{first.display_name} vs. {second.display_name}"
        if winner is None:
            description = status.type.detail or "No winner."
        else:
            method = _method(competition)
            description = f"{winner.display_name} wins" + (
                f" by {method.casefold()}" if method else ""
            )
            if status.period:
                description += f" in round {status.period}"
                if status.display_clock:
                    description += f" at {status.display_clock}"
            description += "."
        weight = (kind.text or kind.abbreviation) if kind is not None else None
        return GameUpdate(key=key, title=names, description=description, when=weight)
    names = f"{sides[0].display_name} vs. {sides[1].display_name}"
    # Tennis: ESPN words each result, such as "(1) Jannik Sinner (ITA) bt Alex de Minaur (AUS) 7-5 6-2".
    note = next((n.text for n in competition.notes if n.text), None)
    if note is None and winner is not None:
        loser = sides[1] if winner is sides[0] else sides[0]
        sets = " ".join(
            f"{w.value:g}-{l.value:g}"
            for w, l in zip(winner.linescores, loser.linescores)
            if w.value is not None and l.value is not None
        )
        note = f"{winner.display_name} beat {loser.display_name} {sets}".strip()
    draw = grouping.display_name if grouping is not None else None
    stage = competition.round.display_name if competition.round is not None else None
    return GameUpdate(
        key=key,
        title=", ".join(part for part in (draw, stage) if part) or names,
        description=note or status.type.detail,
    )


def game_updates(
    sport: Sport, league: str, event: Event, summary: Summary | None = None
) -> list[GameUpdate]:
    """Every update the event's thread can be sent so far, in order.

    :param league: The league's slug, which tells college basketball's halves from the NBA's quarters.
    :param summary: The event's summary, which football's, hockey's and baseball's scoring plays come from.
    """
    status = event.current_status
    if status is None:
        return []
    if sport in RESULT_SPORTS:
        return [
            update
            for grouping, competition in _matches(event)
            if (update := _result(sport, grouping, competition)) is not None
        ]
    if status.state is State.PRE:
        return []
    if status.state is State.POST and not status.type.completed:
        return [
            GameUpdate(
                key=f"status:{status.type.name}",
                title=status.type.description or "Called off",
                description=status.type.detail,
            )
        ]

    updates = [GameUpdate(key="start", title=START_TITLES.get(sport, "Underway"))]
    if sport is Sport.GOLF:
        if status.state is State.POST:
            updates.append(
                GameUpdate(
                    key="final",
                    title=status.type.detail or "Final",
                    description="\n".join(leaderboard(event.competition, 5)) or None,
                )
            )
        return updates

    competition = event.competition
    if competition is None or _sides(competition) is None:
        return updates
    timeline = [
        ((period, 0, index), update)
        for index, (period, update) in enumerate(
            _plays(sport, league, competition, summary)
        )
    ]
    timeline += [
        ((period, 1, 0), update)
        for period, update in _period_ends(sport, league, competition, status)
    ]
    updates += [update for _, update in sorted(timeline, key=lambda item: item[0])]
    if status.state is State.POST:
        updates.append(_final(sport, competition, status))
    return updates


def joined_update(sport: Sport, event: Event) -> GameUpdate | None:
    """Where a game stands, for a thread that starts while it's under way and so skips what came before."""
    status = event.current_status
    if sport in RESULT_SPORTS or status is None or status.state is not State.IN:
        return None
    if sport is Sport.GOLF:
        return GameUpdate(
            key="joined",
            title="Under way",
            description="\n".join(leaderboard(event.competition, 5)) or None,
        )
    return GameUpdate(
        key="joined",
        title="Under way",
        description=status.type.detail,
        score=score_line(event.competition),
    )


def thread_name(event: Event) -> str:
    return truncate(event.short_name or event.name, 100)


# The embeds the commands send, and a watch's message for each game.


def _venue(event: Event) -> str | None:
    competition = event.competition
    venue = (
        (competition.venue if competition is not None else None)
        or event.venue
        or event.circuit
        or (event.venues[0] if event.venues else None)
    )
    if venue is None:
        return None
    address = venue.address
    place = ", ".join(
        part
        for part in (
            (address.city, address.state or address.country) if address else ()
        )
        if part
    )
    name = venue.full_name or venue.short_name
    return " · ".join(part for part in (name, place) if part) or None


def _broadcast(event: Event) -> str | None:
    competition = event.competition
    if competition is None:
        return None
    if competition.broadcast:
        return competition.broadcast
    names = [name for broadcast in competition.broadcasts for name in broadcast.names]
    return ", ".join(dict.fromkeys(names)) or None


def _base(title: str, league: League | None, colour: int | None = None) -> Embed:
    embed = Embed(
        title=truncate(title, 256), colour=colour if colour is not None else ESPN_RED
    )
    if league is not None:
        embed.set_author(
            name=truncate(league.name, 256), url=league.url, icon_url=league.logo_url
        )
    return embed.set_footer(text=CREDIT)


def game_message(event: Event, league: League | None) -> Embed:
    """A watch's message for a game, posted before it starts: who, when and where, and never the score."""
    sides = _sides(event.competition)
    embed = _base(event.name, league, team_colour(sides[1]) if sides else None)
    embed.url = event.url
    notes = event.competition.notes if event.competition is not None else ()
    if note := next((n.headline for n in notes if n.headline), None):
        embed.description = note
    starts = f"{format_dt(event.date, 'F')} ({format_dt(event.date, 'R')})"
    embed.add_field(name="Starts", value=starts, inline=False)
    if event.end_date is not None and event.end_date.date() != event.date.date():
        embed.add_field(name="Ends", value=format_dt(event.end_date, "D"))
    if venue := _venue(event):
        embed.add_field(name="Venue", value=truncate(venue, 1024))
    if broadcast := _broadcast(event):
        embed.add_field(name="Broadcast", value=truncate(broadcast, 1024))
    if sides is not None and league is not None and league.logo_url:
        embed.set_thumbnail(url=league.logo_url)
    return embed


def _ranked(competitor: Competitor) -> str:
    name = _abbreviation(competitor)
    return f"({competitor.ranking}) {name}" if competitor.ranking else name


def _scoreboard_line(sport: Sport, event: Event) -> str:
    status = event.current_status
    sides = (
        _sides(event.competition) if sport not in RESULT_SPORTS | {Sport.GOLF} else None
    )
    state = status.state if status is not None else State.PRE
    if sides is None:
        line = f"**{event.name}**"
        if status is not None and state is not State.PRE:
            line += f" · {status.type.short_detail or status.type.description}"
        else:
            line += f" · {format_dt(event.date, 'f')}"
        if sport is Sport.GOLF and state is not State.PRE:
            leader = leaderboard(event.competition, 1)
            if leader:
                line += f" · {leader[0].removeprefix('1. ')}"
        return line
    away, home = sides
    if state is State.PRE:
        return f"{_ranked(away)} @ {_ranked(home)} · {format_dt(event.date, 'f')}"
    assert status is not None
    names = [_ranked(away), _ranked(home)]
    for index, side in enumerate(sides):
        if side.winner:
            names[index] = f"**{names[index]}**"
    return (
        f"{names[0]} {_score(away)}, {names[1]} {_score(home)} · "
        f"{status.type.short_detail or status.type.description}"
    )


def scoreboard_embed(
    sport: Sport, scoreboard: Scoreboard, league: League | None, key: str
) -> Embed:
    """A league's games for a day or week, with their scores."""
    name = (
        league.name
        if league is not None
        else (scoreboard.league.name if scoreboard.league else key)
    )
    embed = _base(name, league)
    if scoreboard.week is not None and scoreboard.week.text:
        embed.title = truncate(f"{name}: {scoreboard.week.text}", 256)
    elif scoreboard.day is not None:
        embed.title = truncate(
            f"{name}: {scoreboard.day.date:%A, %B} {scoreboard.day.date.day}", 256
        )
    lines = [_scoreboard_line(sport, event) for event in scoreboard.events]
    embed.description = join_lines(lines, 4096) if lines else "No games are listed."
    return embed


def _scoring(
    sport: Sport, league: str, event: Event, summary: Summary | None
) -> list[str]:
    competition = event.competition
    if competition is None:
        return []
    lines = []
    for _, update in _plays(sport, league, competition, summary):
        line = " · ".join(
            part for part in (update.when, update.description or update.title) if part
        )
        if update.score is not None:
            line += f" ({update.score})"
        lines.append(line)
    return lines


def game_embed(
    sport: Sport,
    league_slug: str,
    event: Event,
    summary: Summary | None,
    league: League | None,
) -> Embed:
    """A game's state: its score, line score and scoring plays, or for golf, racing, MMA and tennis, its results."""
    status = event.current_status
    sides = (
        _sides(event.competition) if sport not in RESULT_SPORTS | {Sport.GOLF} else None
    )
    embed = _base(event.name, league, team_colour(sides[1]) if sides else None)
    embed.url = event.url
    if status is not None:
        embed.description = status.type.detail or status.type.description
    if status is None or status.state is State.PRE:
        embed.add_field(
            name="Starts",
            value=f"{format_dt(event.date, 'F')} ({format_dt(event.date, 'R')})",
            inline=False,
        )
        if venue := _venue(event):
            embed.add_field(name="Venue", value=truncate(venue, 1024))
        if broadcast := _broadcast(event):
            embed.add_field(name="Broadcast", value=truncate(broadcast, 1024))
        return embed

    if sides is not None:
        if (score := score_line(event.competition)) is not None:
            embed.add_field(name="Score", value=score, inline=False)
        if (table := line_score(event.competition, sport)) is not None:
            embed.add_field(
                name="Line score", value=truncate(table, 1024), inline=False
            )
        if scoring := _scoring(sport, league_slug, event, summary):
            # The latest plays, which are what fits.
            embed.add_field(
                name="Scoring", value=join_lines(scoring[::-1], 1024), inline=False
            )
    elif sport is Sport.GOLF:
        embed.add_field(
            name="Leaderboard",
            value=join_lines(leaderboard(event.competition, 10), 1024) or "None yet.",
        )
    else:
        results = [
            update
            for grouping, competition in _matches(event)
            if (update := _result(sport, grouping, competition)) is not None
        ]
        for update in results[-10:]:
            embed.add_field(
                name=truncate(update.title, 256),
                value=truncate(update.description or "-", 1024),
                inline=False,
            )
        if not results:
            embed.add_field(name="Results", value="None yet.")
    return embed


def _stat(entry: StandingsEntry, *names: str) -> str | None:
    for name in names:
        if (stat := entry.stat(name)) is not None and stat.display_value not in (
            None,
            "",
            " ",
        ):
            return stat.display_value
    return None


def _number(entry: StandingsEntry, name: str) -> float | None:
    stat = entry.stat(name)
    if stat is None or stat.value is None:
        return None
    try:
        return float(stat.value)
    except ValueError:
        return None


def _standing(entry: StandingsEntry) -> str:
    points = _stat(entry, "points", "championshipPts")
    record = _stat(entry, "overall")
    if points is not None and record is not None:
        return f"{points} pts ({record})"
    if points is not None:
        return f"{points} pts"
    return record or ""


def _sorted_entries(entries: Iterable[StandingsEntry]) -> list[StandingsEntry]:
    entries = list(entries)
    if entries and all(_number(e, "rank") for e in entries):
        return sorted(entries, key=lambda e: _number(e, "rank") or 0)
    if entries and all(_number(e, "points") is not None for e in entries):
        return sorted(entries, key=lambda e: -(_number(e, "points") or 0))
    if entries and all(_number(e, "winPercent") is not None for e in entries):
        return sorted(
            entries,
            key=lambda e: (
                -(_number(e, "winPercent") or 0),
                _number(e, "playoffSeed") or 99,
            ),
        )
    return entries


def standings_embed(standings: Standings, league: League | None, key: str) -> Embed:
    """A league's tables, each as a field."""
    embed = _base(f"{league.name if league else key} standings", league)
    tables = list(standings.tables())
    if not tables:
        embed.description = "ESPN keeps no standings for this league."
        return embed
    length = len(embed.title or "") + len(CREDIT)
    shown = 0
    for group in tables[:25]:
        lines = [
            f"{index}. {entry.display_name}"
            + (f" · {record}" if (record := _standing(entry)) else "")
            for index, entry in enumerate(_sorted_entries(group.entries), start=1)
        ]
        name = truncate(group.name or group.short_name or "Standings", 256)
        value = join_lines(lines, 1024) or "No teams."
        if length + len(name) + len(value) > 5800:
            break
        embed.add_field(name=name, value=value, inline=False)
        length += len(name) + len(value)
        shown += 1
    if shown < len(tables):
        embed.description = f"Showing {shown} of {len(tables)} tables."
    return embed


def news_embed(news: News, league: League | None, key: str) -> Embed:
    embed = _base(f"{league.name if league else key} news", league)
    lines = []
    for article in news.articles:
        link = (
            article.links.web.href
            if article.links is not None and article.links.web is not None
            else None
        )
        headline = (
            f"[{article.headline}]({link})" if link else f"**{article.headline}**"
        )
        lines.append(
            headline + (f"\n{article.description}" if article.description else "")
        )
    embed.description = join_lines(lines, 4096) if lines else "No news."
    return embed


def event_choice(event: Event) -> str:
    """An event as a choice in Discord: its name and status, but not its score."""
    status = event.current_status
    detail = (
        (status.type.short_detail or status.type.description)
        if status is not None
        else None
    )
    return truncate(
        f"{event.short_name or event.name} · {detail}" if detail else event.name, 100
    )


__all__ = [
    "CREDIT",
    "DETAIL_SPORTS",
    "ESPN_RED",
    "FEATURED",
    "RESULT_SPORTS",
    "SPORT_NAMES",
    "SUMMARY_SPORTS",
    "Directory",
    "GameUpdate",
    "event_choice",
    "game_embed",
    "game_message",
    "game_updates",
    "join_lines",
    "joined_update",
    "leaderboard",
    "line_score",
    "needs_summary",
    "news_embed",
    "ordinal",
    "parse_key",
    "period_name",
    "score_line",
    "scoreboard_embed",
    "standings_embed",
    "team_colour",
    "thread_name",
    "truncate",
]
