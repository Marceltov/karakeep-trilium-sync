# Operations

## Logs

The sync logs to stdout, one line per imported bookmark and one per run:

```
INFO imported 'How VLANs work' as gpzpCN7pvxb0
INFO run finished: 1 new note(s)
```

`LOG_LEVEL: DEBUG` adds detail. A failed run is logged as `run failed: …` and retried after `SYNC_INTERVAL`; the container keeps running.

## Run from cron instead

With `SYNC_INTERVAL: "0"` the container runs once and exits, with a non-zero exit code if the run failed. Drop `restart: unless-stopped` and start it from cron or a systemd timer:

```bash
*/30 * * * * docker compose -f /srv/trilium/docker-compose.yml run --rm karakeep-trilium-sync
```

## Updating

```bash
docker compose pull karakeep-trilium-sync && docker compose up -d karakeep-trilium-sync
```

`:latest` follows releases. Pin a version, e.g. `:0.1`, to update only on your terms. Images are built for `linux/amd64` and `linux/arm64`.

## Security

- The image runs as an unprivileged user, needs no volumes and opens no ports.
- The Karakeep API key acts as your Karakeep user, and the ETAPI token has full access to Trilium. Keep both in a gitignored `.env`.
- Your private Reddit feed URLs carry a key. The sync reads them from Karakeep and never logs them.

## Troubleshooting

| Log line | Cause |
|---|---|
| `invalid configuration: KARAKEEP_API_KEY is not set` | A required variable is missing; the container exits with code 2. Check that `.env` is next to the compose file. |
| `invalid configuration: label … must look like #name or #name=value` | Fix `TRILIUM_NOTE_LABELS` or `TRILIUM_FOLDER_LABELS`; see [Labels](configuration.md#labels). |
| `run failed: Client error '401 Unauthorized'` for `…/api/v1/…` | The Karakeep API key is wrong or deleted. |
| `run failed: Client error '401 Unauthorized'` for `…/etapi/…` | The ETAPI token is wrong or deleted. |
| `run failed: Client error '404 Not Found'` for `…/etapi/notes/<id>` | `TRILIUM_PARENT_NOTE` doesn't exist. |
| `TRILIUM_PARENT_SEARCH '…' must find one note, found 0` | No note carries that label, or more than one does. |
| `run failed: … Name or service not known` | The container can't resolve Trilium or Karakeep: check the network, or use public URLs. |
| `Reddit post … unavailable: HTTP 403` or `429` | Reddit refused; the bookmark is retried on the next run. Adding your [saved feed](reddit.md#import-everything-you-save-on-reddit) avoids this for posts you saved. |
| A bookmark never imports, with no error | Karakeep is still crawling it, or it already has the done tag. |
