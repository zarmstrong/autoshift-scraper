# AGENTS.md

Instructions for AI coding agents working in this repository. `CLAUDE.md` is a symlink to this file. Edit this file, not the symlink.

## What this project does

This project scrapes SHiFT codes (Borderlands series, Tiny Tina's Wonderlands) from a few community sites. It merges them with the previously published list and writes an autoshift-compatible `data/shiftcodes.json`. When it runs with GitHub credentials, it commits that file to a separate public repo. Many autoshift clients pull that public repo, so this project's output is live data other people depend on.

## Layout

- `autoshift_scraper.py`: the main entry point and nearly all of the logic.
  - `webpages`: the list of mentalmars pages. Each entry has a `platform_ordered_tables` list that maps each `<table>` on the page, in order, to a platform or to `"discard"`. When mentalmars changes a page layout, this list usually needs updating.
  - `scrape_codes()`: the generic scraper for mentalmars tables.
  - `scrape_polygon_bl4_codes()`, `scrape_ign_bl4_codes()`, `scrape_xsmash_codes()`: site-specific BL4 scrapers. Each takes `existing_codes_set` to de-duplicate.
  - `cleanse_codes()` / `remap_dict_keys()`: normalise scraped rows into `code` / `reward` / `expires` / `expired`.
  - `generateAutoshiftJSON()`: builds the output from this run's scraped codes, keeping each code's previous `archived` date and `expired` flag.
  - `carry_forward_previous_codes()`: called once after all scrapers; appends previously published entries that no source returned this run, so a source outage can't drop codes from the published file.
  - `run_migrations_on_shiftfile()`: upgrades the file format. The current `meta.version` is `"2"`. If you change the output schema, bump the version and add a migration here. Note that versions are compared as strings.
  - `main()` / `setup_argparser()`: CLI flags (`--user`, `--repo`, `--token`, `--schedule`, `--verbose`, ...).
- `mark_expired.py`: a manual tool that forces specific codes to expired in `data/shiftcodes.json` and can optionally push the file.
- `common.py`: the shared logger (`_L`) and path constants. It is derived from Fabbi's autoshift (LGPL), so keep its header.
- `tests/test_parsers.py`: pytest unit tests. They monkeypatch `requests.get` with fixture HTML, so they never touch the network.
- `.github/workflows/scrape.yml`: runs the scraper every 40 minutes on `master` and publishes to the codes repo.
- `.github/workflows/docker-publish.yml`: builds and pushes the Docker Hub image on every push to `master`.
- `Dockerfile`, `cronjob.sh`: container and host scheduling.

## Setup and commands

The project targets Python 3.12 (the version CI and the Dockerfile use).

```bash
pip install -r requirements.txt
pytest tests/                    # required before any change is considered done
python autoshift_scraper.py      # local run: writes data/ only, publishes nothing
```

## Rules

### Never publish to the live codes repo
- Never run `autoshift_scraper.py` or `mark_expired.py` with `--user`, `--repo` or `--token`, and never set `SCRAPER_*` / `GITHUB_*` credentials.
- Never trigger the workflows yourself: no `gh workflow run`, no `cronjob.sh`.
- Any of these would push to the public `shiftcodes.json` that real users consume. Only the maintainer publishes.

### Don't touch generated data
- Don't edit, commit or delete `data/shiftcodes.json` or anything else under `data/`. These files are generated output.
- If you need sample data for a test, write a fixture inside `tests/`.

### Scrape politely
- Don't add loops, retries or extra requests that raise the load on source sites. Keep the existing `timeout=` and `User-Agent: autoshift-scraper/1.0` headers.
- Don't add a new source site without asking first.
- To debug a parser, fetch the page once and save it as a fixture. Don't hit the site repeatedly.

### Testing
- `pytest tests/` must pass before you report a change as done. Report failures honestly.
- When you add or change a scraper or parser, add or update a test in `tests/test_parsers.py` that uses mocked HTML. Follow the existing `monkeypatch` pattern.
- You don't need to scrape the live sites to verify a change.

### Git workflow
- Never commit directly to `master`. Every push to `master` rebuilds and publishes the Docker image, and the scheduled scraper runs from `master`.
- Always work in a git worktree, never in the main checkout at `/opt/autoshift-scraper`. That checkout stays on a clean `master`, because the host cron job (`cronjob.sh`) runs from it.
  ```bash
  git worktree add ../autoshift-scraper-worktrees/<branch> -b <branch> master
  cd ../autoshift-scraper-worktrees/<branch>
  ```
  - Name branches like `fix/xsmash-parser` or `feat/new-source`. Commit in the worktree and open a PR against `master`.
  - `data/` is gitignored, so a new worktree starts without it. `pytest` doesn't need it. A local scraper run does: run `mkdir -p data && echo '[]' > data/shiftcodes.json` inside the worktree. Don't copy or symlink the main checkout's `data/`.
  - After the PR is merged, or the work is abandoned, remove the worktree with `git worktree remove <path>`. Delete the branch only after it has been merged.
- Use Conventional Commit prefixes (`feat:`, `fix:`, `chore:`, `refactor:`, `test:`), matching recent history.

### Code style
- Match the surrounding code. Log through `_L` from `common.py`, not `print`.
- Keep code validation strict: invalid code formats must never reach the output file (see the version 2 migration).
- Don't change the output JSON field names or their meaning without a format version bump and a migration. Downstream autoshift clients parse this file.
