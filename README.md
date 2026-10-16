# karakeep-trilium-sync

Copies bookmarks from [Karakeep](https://karakeep.app) into [Trilium](https://triliumnotes.org) as notes. Tag a bookmark `trilium` in Karakeep, from the browser extension or the phone's share sheet, and within one sync interval it shows up in Trilium with the article text Karakeep saved.

It's one small container that polls both REST APIs. It needs a Karakeep API key and a Trilium ETAPI token, and no public endpoint.

## Quick start

```yaml
services:
  karakeep-trilium-sync:
    image: ghcr.io/marceltov/karakeep-trilium-sync:latest
    container_name: karakeep-trilium-sync
    restart: unless-stopped
    environment:
      KARAKEEP_API_ADDR: https://karakeep.example.com
      KARAKEEP_API_KEY: ${KARAKEEP_API_KEY}
      TRILIUM_SERVER_URL: http://trilium:8080
      TRILIUM_ETAPI_TOKEN: ${TRILIUM_ETAPI_TOKEN}
      TRILIUM_PARENT_NOTE: abc123XYZ   # the note to put bookmarks under
```

Create the Karakeep API key under *Settings → API Keys* and the ETAPI token under Trilium's *Options → ETAPI*. Keep both in a gitignored `.env`. Run it on the same Docker network as Trilium, or point `TRILIUM_SERVER_URL` at Trilium's public URL.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `KARAKEEP_API_ADDR` | required | Karakeep base URL, without `/api/v1` |
| `KARAKEEP_API_KEY` | required | Karakeep API key |
| `KARAKEEP_TAG` | `trilium` | Import bookmarks with this tag |
| `KARAKEEP_LIST` | | Import the bookmarks in this list instead of a tag |
| `KARAKEEP_DONE_TAG` | `trilium-imported` | Tag set on a bookmark once imported; empty sets none |
| `TRILIUM_SERVER_URL` | `http://trilium:8080` | Trilium base URL; `/etapi` is appended |
| `TRILIUM_ETAPI_TOKEN` | required | ETAPI token the sync writes with |
| `TRILIUM_PARENT_NOTE` | `root` | Note ID to create the notes under |
| `TRILIUM_PARENT_SEARCH` | | A Trilium search that finds the parent note instead, e.g. `#bookmarks`; it must find exactly one note |
| `TRILIUM_FOLDER` | | Subfolder path below the parent, as [strftime](https://docs.python.org/3/library/datetime.html#strftime-and-strptime-format-codes) of the import date: `%Y`, `%Y/%m`, `%Y-W%V`. Empty puts notes directly under the parent |
| `TRILIUM_FOLDER_LABELS` | | Labels for folders the sync creates, in Trilium's syntax; `{name}` is the folder's title. E.g. `#iconClass="bx bx-folder"` |
| `TRILIUM_NOTE_LABELS` | | Extra labels on every imported note, e.g. `#unread #source=karakeep` |
| `REDDIT_FEEDS` | `true` | Take Reddit posts from Reddit's feeds (see below) |
| `SYNC_INTERVAL` | `900` | Seconds between runs; `0` runs once and exits (non-zero on failure), for cron |
| `LOG_LEVEL` | `INFO` | Python log level |

A folder is any existing child note with the folder's title, so the sync reuses folders you made by hand.

## What a bookmark becomes

| Bookmark | Note content | Labels |
|---|---|---|
| Link, crawled | Source link, author, publisher and publish date, then the article as Karakeep extracted it | `#karakeepId`, `#sourceUrl`, `#fetchedOn` (crawl date), `#fetchedVia=karakeep` |
| Link, crawl failed | Just the source link | `#karakeepId`, `#sourceUrl` |
| Link, still crawling | Nothing yet; retried on the next run | |
| Text | The text, as paragraphs | `#karakeepId`, `#sourceUrl` if set |
| PDF or image | The text Karakeep extracted; the file stays in Karakeep | `#karakeepId`, `#sourceUrl` if set, `#fetchedOn`, `#fetchedVia=karakeep` |

The bookmark's own note, if you wrote one, is quoted at the top. Images in the article stay links to their original URLs. `TRILIUM_NOTE_LABELS` are added after these.

Each bookmark is imported once. After importing, the sync tags it `KARAKEEP_DONE_TAG` and skips it from then on. A bookmark that already has a note with its `#karakeepId` below the parent is never imported again, even if tagging it failed or the done tag is empty.

### Reddit

Reddit shows crawlers, Karakeep's included, a cookie and login page instead of the post. With `REDDIT_FEEDS` on, the sync ignores Karakeep's capture of a Reddit post and takes it from Reddit itself:

1. From your private Reddit feeds that Karakeep subscribes to, such as your saved posts (`https://www.reddit.com/saved.rss?feed=…&user=…`, from [reddit.com/prefs/feeds](https://www.reddit.com/prefs/feeds/)). Their key lets them through, and each entry carries the post's text. They hold your most recent saves (about 25), without comments. Labelled `#fetchedVia=reddit-feed`.
2. Otherwise from the post's own public feed, which adds the comments but allows only about one anonymous request a minute. Labelled `#fetchedVia=reddit-post-feed`.

If Reddit refuses both, the bookmark waits for the next run. To import everything you save on Reddit, add a Karakeep rule that tags bookmarks from the Reddit feed with your import tag.

## Example: an LLM wiki's sources

For a wiki whose sources live under a note labelled `#llmWikiPart=sources`, in one folder per year:

```yaml
      TRILIUM_PARENT_SEARCH: "#llmWikiPart=sources"
      TRILIUM_FOLDER: "%Y"
      TRILIUM_FOLDER_LABELS: '#wikiSourceGroup={name} #iconClass="bx bx-folder"'
```

## Development

```bash
uv run pytest -q                      # unit tests against fake Karakeep/Trilium APIs
docker build -t karakeep-trilium-sync .
```

Every branch push publishes `ghcr.io/marceltov/karakeep-trilium-sync:<branch>`; a `v*` tag publishes the versioned release and `:latest`.

## License

AGPL-3.0-or-later.
