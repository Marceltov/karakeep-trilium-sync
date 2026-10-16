# Getting started

This guide takes you from nothing to bookmarks arriving in Trilium. It assumes Karakeep and Trilium are already running and that you run containers with Docker Compose. Setup takes about ten minutes.

## 1. Create a Karakeep API key

In Karakeep, open *Settings → API Keys*, create a key named e.g. `trilium-sync`, and copy it. Karakeep shows it only once.

The key acts as your Karakeep user: the sync reads that user's bookmarks, tags and RSS subscriptions and adds the done tag.

## 2. Create a Trilium ETAPI token

In Trilium, open *Options → ETAPI*, choose *Create new ETAPI token*, name it e.g. `karakeep-sync`, and copy it.

## 3. Choose where the notes go

The sync puts every imported bookmark below one parent note. Pick or create that note, e.g. *Bookmarks*, and point the sync at it in one of two ways:

- **By note ID** (`TRILIUM_PARENT_NOTE`). Open the note; *Note Info* in the ribbon shows its ID, e.g. `abc123XYZ`. The ID is also the last part of the note's URL, after the final `/`.
- **By label** (`TRILIUM_PARENT_SEARCH`). Give the note a label, e.g. `#bookmarkInbox`, and set `TRILIUM_PARENT_SEARCH: "#bookmarkInbox"`. This keeps working when you move the note. The search must find exactly one note, or each run fails with an error.

Without either, notes go straight into the root of your tree.

Optionally, sort them into folders by import date with `TRILIUM_FOLDER`, e.g. `%Y` for one folder per year or `%Y/%m` for year and month. See [Folders](configuration.md#folders).

## 4. Add the container

Put both secrets in a `.env` file next to your compose file, and keep it out of git:

```bash
KARAKEEP_API_KEY=ak2_...
TRILIUM_ETAPI_TOKEN=...
```

Then add the service:

=== "Same project as Trilium"

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

=== "Separate project"

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

=== "Public URLs"

    The sync only makes outgoing requests, so it can run anywhere that reaches both services over HTTPS:

    ```yaml
    services:
      karakeep-trilium-sync:
        image: ghcr.io/marceltov/karakeep-trilium-sync:latest
        container_name: karakeep-trilium-sync
        restart: unless-stopped
        environment:
          KARAKEEP_API_ADDR: https://karakeep.example.com
          KARAKEEP_API_KEY: ${KARAKEEP_API_KEY}
          TRILIUM_SERVER_URL: https://trilium.example.com
          TRILIUM_ETAPI_TOKEN: ${TRILIUM_ETAPI_TOKEN}
          TRILIUM_PARENT_NOTE: abc123XYZ
    ```

All settings are on the [Configuration](configuration.md) page.

## 5. Start it and check the log

```bash
docker compose up -d karakeep-trilium-sync
docker logs -f karakeep-trilium-sync
```

A healthy run logs one line every `SYNC_INTERVAL` (15 minutes by default):

```
INFO run finished: 0 new note(s)
```

Before you tag anything it says `no Karakeep tag 'trilium' yet; nothing to import` instead. That's fine too. If the log shows an error, see [Troubleshooting](operations.md#troubleshooting).

## 6. Try it

Tag a bookmark `trilium` in Karakeep and wait for Karakeep to finish crawling it. On the next run the log shows `imported '<title>' as <noteId>`, the note appears in Trilium, and the bookmark gets the tag `trilium-imported`.

To skip the wait, restart the container: it runs once at startup.

```bash
docker restart karakeep-trilium-sync
```

## Next steps

- Save on Reddit and have it land in Trilium: [Reddit](reddit.md).
- See what each kind of bookmark turns into: [What gets imported](what-gets-imported.md).
- Run it from cron, update it, fix errors: [Operations](operations.md).
