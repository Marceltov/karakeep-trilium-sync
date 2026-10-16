# Contributing

The sync is one module, `karakeep_sync.py`, with unit tests that run it against in-memory fakes of the Karakeep and Trilium APIs. No running services are needed.

```bash
uv run pytest -q                        # unit tests
docker build -t karakeep-trilium-sync . # the image
```

To try a change against real services, run the image once:

```bash
docker run --rm --env-file .env -e SYNC_INTERVAL=0 karakeep-trilium-sync
```

Preview the docs with:

```bash
uvx --with mkdocs-material --with 'mkdocs<2' mkdocs serve
```

## Releases

Every branch push runs the tests and publishes `ghcr.io/marceltov/karakeep-trilium-sync:<branch>`. An annotated `v*` tag publishes `:1.2.3`, `:1.2`, `:1` and `:latest`, and a GitHub release whose notes are the tag message:

```bash
git tag -a v0.2.0 -m "What changed"
git push origin v0.2.0
```

Pushes to `main` that touch `docs/` rebuild this site.
