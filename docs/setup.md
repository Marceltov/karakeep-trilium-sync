# Setting it up

This guide takes you from nothing to bookmarks arriving in Trilium. It assumes Karakeep and Trilium are already running and that you run containers with Docker Compose. Setup takes about ten minutes.

## 1. Create a Karakeep API key

In Karakeep, open *Settings → API Keys*, create a key named e.g. `trilium-sync`, and copy it. Karakeep shows it only once.

The key acts as your Karakeep user: the sync reads that user's bookmarks, tags and RSS subscriptions and adds the done tag.

## 2. Create a Trilium ETAPI token

In Trilium, open *Options → ETAPI*, choose *Create new ETAPI token*, name it e.g. `karakeep-sync`, and copy it.

## 3. Choose where the notes go

The sync puts every imported bookmark below one parent note. Pick or create that note, e.g. *Bookmarks*, and point the sync at it in one of two ways:

- **By note ID** (`TRILIUM_PARENT_NOTE`). Open the note, then *Note Info* in the ribbon shows its ID, e.g. `abc123XYZ`. The ID is also the last part of the note's URL, after the final `/`.
- **By label** (`TRILIUM_PARENT_SEARCH`). Give the note a label, e.g. `#bookmarkInbox`, and set `TRILIUM_PARENT_SEARCH: "#bookmarkInbox"`. This survives moving the note around. The search must find exactly one note, or each run fails with an error.

Without either, notes go straight into the root of your tree.

Optionally, sort them into folders by import date with `TRILIUM_FOLDER`, e.g. `%Y` for one folder per year or `%Y/%m` for year and month. Existing child notes with a matching title are reused, so you can create the folders yourself.

## 4. Add the container

Put both secrets in a `.env` file next to your compose file, and keep it out of git:

```bash
KARAKEEP_API_KEY=ak2_...
TRILIUM_ETAPI_TOKEN=...
```

### Same compose project as Trilium

If Trilium is in the same `docker-compose.yml`, add a service; it reaches Trilium by service name:

```yaml
services:
  trilium:
    # ... your existing Trilium service ...

  karakeep-trilium-sync:
    image: ghcr.io/marceltov/karakeep-trilium-sync:latest
    container_name: karakeep-trilium-sync
    restart: unless-stopped
    environment:
      KARAKEEP_API_ADDR: https://karakeep.example.com
      KARAKEEP_API_KEY: ${KARAKEEP_API_KEY}
      TRILIUM_SERVER_URL: http://trilium:8080
      TRILIUM_ETAPI_TOKEN: ${TRILIUM_ETAPI_TOKEN}
      TRILIUM_PARENT_NOTE: abc123XYZ
      TRILIUM_FOLDER: "%Y"
```

### Separate compose project

Otherwise, join Trilium's network. `docker network ls` lists it, usually `<trilium project>_default`:

```yaml
services:
  karakeep-trilium-sync:
    image: ghcr.io/marceltov/karakeep-trilium-sync:latest
    container_name: karakeep-trilium-sync
    restart: unless-stopped
    environment:
      KARAKEEP_API_ADDR: https://karakeep.example.com
      KARAKEEP_API_KEY: ${KARAKEEP_API_KEY}
      TRILIUM_SERVER_URL: http://trilium:8080   # Trilium's container name
      TRILIUM_ETAPI_TOKEN: ${TRILIUM_ETAPI_TOKEN}
      TRILIUM_PARENT_NOTE: abc123XYZ
    networks: [trilium]

networks:
  trilium:
    external: true
    name: trilium_default
```

Instead of joining the network you can also set `TRILIUM_SERVER_URL` to Trilium's public HTTPS address. `KARAKEEP_API_ADDR` works the same way: Karakeep's public URL, or its container name on a shared network.

All settings are listed in the [README](../README.md#configuration).

## 5. Start it and check the log

```bash
docker compose up -d karakeep-trilium-sync
docker logs -f karakeep-trilium-sync
```

A healthy run logs one line every `SYNC_INTERVAL` (15 minutes by default):

```
INFO run finished: 0 new note(s)
```

Before you tag anything it says `no Karakeep tag 'trilium' yet; nothing to import` instead. That's fine too.

## 6. Try it

Tag a bookmark `trilium` in Karakeep and wait for Karakeep to finish crawling it. On the next run the log shows `imported '<title>' as <noteId>`, the note appears in Trilium, and the bookmark gets the tag `trilium-imported`.

To skip the wait, restart the container: it runs once at startup.

```bash
docker restart karakeep-trilium-sync
```

## Optional: import your Reddit saves automatically

Reddit hides posts from crawlers behind a login page, so the sync reads Reddit posts from Reddit's feeds instead. Your private saved-posts feed works best, and Karakeep can also import from it:

1. On [reddit.com/prefs/feeds](https://www.reddit.com/prefs/feeds/), copy the RSS link of your *saved links*. It looks like `https://www.reddit.com/saved.rss?feed=…&user=…`. Treat it like a password.
2. In Karakeep, open *Settings → RSS Subscriptions* and add that URL. Karakeep now creates a bookmark for each post you save on Reddit.
3. In Karakeep's rule engine, under *Settings*, add a rule: when a bookmark is added and it was imported from that feed, add the tag `trilium`.

Every post you save on Reddit then ends up in Trilium, with its text. Posts you share to Karakeep from the Reddit app work too, but come from the post's public feed, which Reddit rate-limits to about one request a minute. Set `REDDIT_FEEDS: "false"` to keep Karakeep's own capture instead.

## Optional: run from cron instead

With `SYNC_INTERVAL: "0"` the container runs once and exits, with a non-zero exit code if the run failed. Drop `restart: unless-stopped` and start it from cron or a systemd timer:

```bash
*/30 * * * * docker compose -f /srv/trilium/docker-compose.yml run --rm karakeep-trilium-sync
```

## Updating

```bash
docker compose pull karakeep-trilium-sync && docker compose up -d karakeep-trilium-sync
```

`:latest` follows releases. Pin a version, e.g. `:0.1`, to update only on your terms.

## Troubleshooting

| Log line | Cause |
|---|---|
| `invalid configuration: KARAKEEP_API_KEY is not set` | A required variable is missing; the container exits with code 2. Check `.env` is next to the compose file. |
| `run failed: Client error '401 Unauthorized'` for `…/api/v1/…` | The Karakeep API key is wrong or deleted. |
| `run failed: Client error '401 Unauthorized'` for `…/etapi/…` | The ETAPI token is wrong or deleted. |
| `run failed: Client error '404 Not Found'` for `…/etapi/notes/<id>` | `TRILIUM_PARENT_NOTE` doesn't exist. |
| `TRILIUM_PARENT_SEARCH '…' must find one note, found 0` | No note carries that label, or more than one does. |
| `run failed: … Name or service not known` | The container can't resolve Trilium or Karakeep: check the network or use public URLs. |
| `Reddit post … unavailable: HTTP 403` / `429` | Reddit refused; the bookmark is retried on the next run. Adding your saved feed (above) avoids this for posts you saved. |
| A bookmark never imports, with no error | Karakeep is still crawling it, or it already has the done tag. |

A note is never created twice for the same bookmark. To re-import one, delete its note in Trilium, then remove the done tag in Karakeep.
