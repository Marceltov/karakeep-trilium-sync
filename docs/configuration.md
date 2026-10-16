# Configuration

All configuration is environment variables. Only the addresses and credentials of the two services are needed; everything else has a default.

## Variables

### Karakeep

| Variable | Default | Meaning |
|---|---|---|
| `KARAKEEP_API_ADDR` | required | Karakeep base URL, without `/api/v1` |
| `KARAKEEP_API_KEY` | required | Karakeep API key, from *Settings → API Keys* |
| `KARAKEEP_TAG` | `trilium` | Import bookmarks with this tag |
| `KARAKEEP_LIST` | | Import the bookmarks in this list instead of a tag |
| `KARAKEEP_DONE_TAG` | `trilium-imported` | Tag set on a bookmark once imported; empty sets none |

### Trilium

| Variable | Default | Meaning |
|---|---|---|
| `TRILIUM_SERVER_URL` | `http://trilium:8080` | Trilium base URL; `/etapi` is appended |
| `TRILIUM_ETAPI_TOKEN` | required | ETAPI token the sync writes with |
| `TRILIUM_PARENT_NOTE` | `root` | Note ID to create the notes under |
| `TRILIUM_PARENT_SEARCH` | | A Trilium search that finds the parent note instead, e.g. `#bookmarkInbox`; it must find exactly one note |
| `TRILIUM_FOLDER` | | Subfolder path below the parent, as a date pattern; empty puts notes directly under the parent. See [Folders](#folders) |
| `TRILIUM_FOLDER_LABELS` | | Labels for folders the sync creates; `{name}` is the folder's title |
| `TRILIUM_NOTE_LABELS` | | Extra labels on every imported note |

### Behaviour

| Variable | Default | Meaning |
|---|---|---|
| `REDDIT_FEEDS` | `true` | Take Reddit posts from Reddit's feeds; see [Reddit](reddit.md) |
| `SYNC_INTERVAL` | `900` | Seconds between runs; `0` runs once and exits (non-zero on failure), for cron |
| `LOG_LEVEL` | `INFO` | Python log level, e.g. `DEBUG` |

An invalid setting, such as a missing key or a malformed label, stops the container at startup with `invalid configuration: …` and exit code 2.

## Choosing bookmarks

By default the sync imports bookmarks tagged `KARAKEEP_TAG`. Set `KARAKEEP_LIST` to the name of a Karakeep list to import that list instead; the tag is then ignored. If the tag or list doesn't exist yet, the run logs that and imports nothing.

The done tag shows you in Karakeep what's been imported, and lets the sync skip those bookmarks cheaply. With `KARAKEEP_DONE_TAG` empty, nothing is tagged and the sync relies on the `#karakeepId` labels alone, which costs one Trilium search per bookmark per run.

## Folders

`TRILIUM_FOLDER` is a path of folder titles below the parent, separated by `/`, written as a Python [strftime](https://docs.python.org/3/library/datetime.html#strftime-and-strptime-format-codes) pattern of the import date:

| `TRILIUM_FOLDER` | Imported on 16 Oct 2026, the note goes to |
|---|---|
| (empty) | *Parent* |
| `%Y` | *Parent / 2026* |
| `%Y/%m` | *Parent / 2026 / 10* |
| `%Y/%m %B` | *Parent / 2026 / 10 October* |
| `%G-W%V` | *Parent / 2026-W42* |
| `Inbox` | *Parent / Inbox* |

A folder is any child note with the folder's title, so the sync reuses folders you made yourself. Missing ones are created as empty text notes.

## Labels

`TRILIUM_FOLDER_LABELS` and `TRILIUM_NOTE_LABELS` use Trilium's label syntax, separated by spaces; quote values that contain spaces:

```yaml
TRILIUM_NOTE_LABELS: '#unread #importedFrom=karakeep'
TRILIUM_FOLDER_LABELS: '#iconClass="bx bx-folder" #sorted'
```

In folder labels, `{name}` is replaced by the folder's title, e.g. `#year={name}`. Note labels are added after the sync's own labels (see [What gets imported](what-gets-imported.md)). Relations (`~name=…`) aren't supported.

## Examples

### A bookmark inbox

Everything tagged `trilium` lands in one note, by month, marked unread:

```yaml
TRILIUM_PARENT_SEARCH: "#bookmarkInbox"
TRILIUM_FOLDER: "%Y/%m"
TRILIUM_NOTE_LABELS: "#unread"
```

### A reading list

Import a Karakeep list called *Read later* instead of a tag, without tagging the bookmarks:

```yaml
KARAKEEP_LIST: Read later
KARAKEEP_DONE_TAG: ""
TRILIUM_PARENT_NOTE: abc123XYZ
```

### An LLM wiki's sources

For an [LLM wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) whose raw sources live under a note labelled `#llmWikiPart=sources`, in one folder per year:

```yaml
TRILIUM_PARENT_SEARCH: "#llmWikiPart=sources"
TRILIUM_FOLDER: "%Y"
TRILIUM_FOLDER_LABELS: '#wikiSourceGroup={name} #iconClass="bx bx-folder"'
```

The wiki's ingest then picks the notes up like any other source. The `#sourceUrl`, `#fetchedOn` and `#fetchedVia` labels the sync sets tell it where the text came from, and a note without `#fetchedVia` is a link-only source that ingest fetches itself.
