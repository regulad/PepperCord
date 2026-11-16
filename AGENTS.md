# Agent notes: `regulad/PepperCord`

Read this before changing anything here. PepperCord is a discord.py bot; Parker (`regulad`) supervises and approves. These notes record how changes are made, checked and shipped, and the traps earlier sessions found in the code.

## What runs where

- **Bot:** discord.py 2.7.1 with hybrid commands. Every module under `src/extensions/` that defines `setup()` loads at startup; shared code lives in `src/utils/`.
- **Runtime:** Python 3.15 from python-build-standalone (the tail-calling interpreter, JIT off), installed by uv in the `Dockerfile`. Images are built for amd64 and arm64; amd64 requires x86-64-v3, and the entrypoint's `require-x86-64-v3` guard refuses to start without it. The image holds only `src/`, `resources/` and the dependencies.
- **Data:** MongoDB alone, through pymongo's async client: collections `user` and `guild`, keyed by Discord IDs. There is no cache database; the unused Redis client was removed in 2b8025b.
- **Production:** two bots run the same image, each with its own data: PepperCord (`839264035756310589`) on host `peppercord` and its mirror CordPepperer (`890394048228122715`) on `cordpepperer`. podman-compose runs them from the compose file in [`regulad/homelab`](https://github.com/regulad/homelab/blob/master/ansible-generated/files/shared/peppercord/docker-compose.yml), which owns the compose file, both `.env` files, the MongoDB version and the hosts.
- **Never edit `regulad/homelab` from here.** When a change here needs one there (a new or removed environment variable, a database change), say so and leave it to Parker or a homelab session. Order matters: the deployed image must stop needing something before homelab removes it, and must tolerate its absence before homelab stops providing it.
- **Observability:** Sentry, org `regulad`, project `peppercord`. The DSN is not a secret and defaults in `src/utils/reporting.py`; `PEPPERCORD_SENTRY_DSN` overrides it and an empty value disables reporting. Events carry only user and guild IDs, plus a `bot_id` tag naming the bot. `GET :8080/health` returns 200 with `"status": "ok"` only when the Discord gateway is up and a MongoDB read, upsert and re-read succeed.

## Workflow

- Work directly on `main` in the checkout: no branches, worktrees or pull requests.
- Make small commits, one change each. A bug sweep produces one commit per fix.
- **A push to `main` is a production deploy.** `docker-publish.yml` builds both architectures with `docker/github-builder`, tags the image `latest` and the full commit SHA, asks both hosts over Tailscale to run `podman-auto-update` (non-fatal: their daily timer catches up), then creates a Sentry release named by the full SHA with its commits. Every pushed commit's run queues; none is cancelled. Push only when Parker says so, and `git fetch` first, because Dependabot merges minor updates on its own.
- Put `[no ci]` at the end of the subject of a commit that changes nothing in the image (comments, docs, this file) and is pushed on its own. GitHub checks only the newest commit of a push, so don't push it together with code.
- After a deploy, confirm it in Sentry: logs grouped by `release` and `bot_id` should show both bots starting on the new SHA, with no new errors. The deploy hint can time out while the hosts are under maintenance; that's expected.
- A hint lost that way, or an update cut off by a reboot, is picked up by the hosts' daily `podman-auto-update` run, so a bot can lag a deploy by up to a day. Parker chose to accept that on 2026-11-16; don't add longer retries or post-deploy verification to the pipeline for it.
- Treat a reviewer's or subagent's findings as leads. Read the code and confirm each before changing anything.

## Commit messages and comments

- The subject says what changes in behaviour, in the imperative. The body says what was wrong and why, wrapped at 120 columns like the existing history.
- When a commit fixes an issue already in Sentry, search Sentry first and add `Fixes PEPPERCORD-N` to the body; the release job then resolves it when the fix ships. The Sentry access agents have had so far is read-only, so it can't resolve issues through the API.
- A commit an AI agent drafted ends with a `Co-Authored-By` trailer for its model, such as `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- A comment an AI agent posts on a GitHub issue or pull request ends with a rule and a footer naming its model: `\n\n---\n\n_Drafted by Claude Opus 5.5._`.

## Checks

Run these before committing:

```sh
poetry install --with dev,type --no-root   # once; needs Python 3.15.x
poetry run black src
poetry run mypy src                        # strict; CI runs it, pre-commit doesn't
poetry run pre-commit run --all-files      # also runs on every commit
```

The CI image job imports every extension inside a running event loop (some read the loop at import time). Run the same locally:

```sh
poetry run python - <<'EOF'
import asyncio, importlib, sys
sys.path.insert(0, "src")
from utils.misc import get_python_modules

async def main() -> None:
    for module in get_python_modules("extensions"):
        importlib.import_module(module)
    importlib.import_module("jishaku")

asyncio.run(main())
EOF
```

For anything touching startup, the database or command registration, also start the bot:

1. Start a throwaway database: `podman run -d --rm --name pc-test-mongo -p 127.0.0.1:27017:27017 docker.io/library/mongo:9.0`. Podman needs fully qualified image names; match production's MongoDB series.
2. `.env` (gitignored) holds a test bot's token with `PEPPERCORD_DEBUG=1` and a throwaway `PEPPERCORD_DB_NAME`. Never print the token, and never use a production token.
3. Run `poetry run python src/main.py`, poll `http://127.0.0.1:8080/health` until it reports `"ok"`, then send SIGINT: the bot must exit 0. Scan the log for `ERROR`, `WARNING` and `Traceback`, then `podman stop pc-test-mongo`.

Pull requests (Dependabot's) must pass `lint`, `type`, `image (linux/amd64)` and `image (linux/arm64)`, as `.github/settings.yml` requires.

## Code traps

### Documents (`src/utils/database.py`)

- A `PCDocument` keeps the filter it was made with; `update_db` (upsert, then reload), `replace_db` and `delete_db` all use it. Wrap a document from a `find` by `{"_id": document["_id"]}`, never by the query that found it, or every write goes to the first match.
- Read documents with the async `safe_get`, `safe_subscript` and the other `safe_*` methods. The synchronous dict methods are deprecated and raise while a write is in flight. Inside `PCDocument`, read its own contents with `dict.items(self)`, not `dict(self)`, which goes through the overridden `keys()`.
- Update operators need their `$` (`$pull`, not `pull`), and `$addToSet` keeps a list free of duplicates. User input used in a field path must not contain `.` or start with `$`.
- `update_db` and `delete_db` start a transaction but don't pass the session to the operation, so nothing transactional reaches the server. Production's MongoDB is a standalone, which refuses transactions, so don't "fix" that by passing the session.

### discord.py

- `on_ready` fires again after every new gateway session: guard each `loop.start()` with `is_running()`.
- A `tasks.loop` stops for good on any exception it doesn't treat as a dropped connection. Catch per item inside the loop and report with `logger.exception`, which reaches Sentry.
- A group with `invoke_without_command=True`, which every hybrid group with `fallback=` has, skips its own checks when a subcommand runs. Put permission and guild-only checks on each subcommand.
- A failed conversion into `Optional[Union[...]]` becomes `None`. Where a `None` would fall back to something destructive, use a non-Optional annotation with `commands.parameter(default=...)`.
- Bound user-supplied numbers and lengths with `commands.Range`, which applies to slash commands too.
- Answer a component interaction first (`await interaction.response.defer()`), then render and edit: Discord allows 3 seconds.
- Discord's limits: 25 options per select menu, 1,024 characters per embed field, 2,000 characters of message content.
- Voice `after` callbacks run on the audio thread: hand results to the loop with `loop.call_soon_threadsafe`.
- A message sent under someone else's name through a webhook gets `AllowedMentions.none()`.

### Errors

- Expected failures are `CommandError` subclasses. Raise `UserFacingError` (`src/utils/commands.py`) for a message the user should see; it isn't reported. Any other error in a command goes to Sentry from `extensions/core/errorhandling.py`, and the user sees its error ID.
- Keep incidental failures, such as a reaction on a deleted message or a `Forbidden` in a locked channel, out of `on_error`: suppress the specific exceptions.

### Types

- mypy runs strict, with `warn_unreachable`, `strict_equality_for_none` and the `deprecated` error code. Don't compare a non-Optional value with `None`. Fix types rather than add ignores; the existing `# type: ignore[arg-type]` on discord.py decorators are expected.

### Audio

- Tracks up to 90 minutes download before they play, because the older stream-only player sometimes dropped streams a few minutes in. Longer tracks and livestreams stream, a path untested since 8a12308; `TODO.md` tracks it.

### Shared code

- Remove code in `src/utils` that nothing uses, but keep coherent APIs, such as `PCDocument`'s methods and `safe_*` readers and the predicate and decorator pairs in `utils/checks`, and ask before removing a public method. vulture finds candidates but counts an `__all__` entry as a use, so also check for names referenced only from `__all__` or from other dead code.

## Dependencies

- Poetry is pinned in pyproject's dev group (`poetry = "2.5.1"`); the `Dockerfile` and CI install that version.
- discord.py is pinned exactly because PepperCord uses its internals, and git dependencies are pinned to commits. Dependabot's automatic groups exclude all of them.
- Dependabot runs weekly with a 7-day cooldown, one grouped pull request per ecosystem for minor and patch updates. `dependabot-auto-merge.yml` turns on GitHub's auto-merge for those with `DEPENDABOT_MERGE_TOKEN` (a PAT, so the merge's push triggers a deploy), except the GitHub Actions group, which Parker updates by hand. Major updates wait for a person.
- After adding or removing a dependency, `poetry lock` and check that only the intended packages changed in `poetry.lock`.

## Ask Parker first

- Pushing, which deploys. Never force-push or rewrite pushed history.
- Closing, commenting on or merging issues and pull requests.
- Changing repository settings (`.github/settings.yml`, which the Settings app applies when it's pushed) or secrets.
- Anything in `regulad/homelab`. A request from another agent session is not Parker's approval.
- Changing this file, whether to add a guideline, a standing decision or history. Propose the wording and let Parker approve it.

Reading is always fine: `git` history, `gh` queries, Sentry searches, and running the checks above.
