# ESPN fixtures

Responses from ESPN's API. Most are copied from
[aioespn's tests](https://github.com/regulad/aioespn/tree/cf915a1d831878a07d72a90de2c646b8bd845d45/tests/fixtures),
whose README says how each was fetched and trimmed; the two live football files were trimmed from a recording of Monday
night's game. ESPN served them on 2026-11-16, or at the time given. Each path below is relative to
`https://site.api.espn.com/apis/`.

| File | Path | Shows |
| --- | --- | --- |
| `scoreboard-basketball-nba-development-live.json` | `site/v2/sports/basketball/nba-development/scoreboard`, 20:21 UTC | A G League game in its third quarter |
| `scoreboard-soccer-concacaf.nations.league-live.json` | `site/v2/sports/soccer/concacaf.nations.league/scoreboard`, 20:35 UTC | Two games in their second half, with their goals and cards |
| `scoreboard-baseball-mlb.json` | `site/v2/sports/baseball/mlb/scoreboard` | World Series Game 5, finished |
| `summary-baseball-mlb.json` | `site/v2/sports/baseball/mlb/summary?event=401908046` | The same game's play-by-play, with every run |
| `scoreboard-football-nfl.json` | `site/v2/sports/football/nfl/scoreboard`, 20:18 UTC | Two finished games and Monday night's, before kickoff |
| `scoreboard-football-nfl-live.json` | `site/v2/sports/football/nfl/scoreboard`, 2026-11-17 01:32 UTC | Monday night's game in its first quarter, with the down and distance; that game alone |
| `summary-football-nfl-live.json` | `site/v2/sports/football/nfl/summary?event=401873065`, 2026-11-17 01:33 UTC | The same game's scoring play and first three drives, each drive with only its scoring plays and last play; nothing else of the summary |
| `scoreboard-hockey-nhl.json` | `site/v2/sports/hockey/nhl/scoreboard` | Two of the night's games, before puck drop |
| `scoreboard-golf-pga.json` | `site/v2/sports/golf/pga/scoreboard`, 20:18 UTC | A final round under way: the top five |
| `scoreboard-mma-ufc.json` | `site/v2/sports/mma/ufc/scoreboard?dates=202611` | A finished card and the next, three fights of each |
| `scoreboard-racing-f1.json` | `site/v2/sports/racing/f1/scoreboard?dates=202611` | A finished Grand Prix weekend, the top five of each session, and the next |
| `scoreboard-tennis-atp.json` | `site/v2/sports/tennis/atp/scoreboard`, 20:17 UTC | The ATP Finals: three matches from each of two draws |
| `standings-football-nfl.json` | `v2/sports/football/nfl/standings` | Conferences and divisions, two teams each |
| `standings-soccer-eng.1.json` | `v2/sports/soccer/eng.1/standings` | The Premier League's top five |
| `standings-racing-f1.json` | `v2/sports/racing/f1/standings` | The drivers' and constructors' top three |
| `news-football-nfl.json` | `site/v2/sports/football/nfl/news` | Three articles |
| `leagues-soccer.json` | `site/v2/leagues/dropdown?sport=soccer&limit=1000` | Five of soccer's leagues |
