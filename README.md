<p align="center"><img src="docs/logo.svg" width="120" alt=""></p>

# karakeep-trilium-sync

Copies bookmarks from [Karakeep](https://karakeep.app) into [Trilium](https://triliumnotes.org) as notes. Tag a bookmark `trilium` in Karakeep, from the browser extension or the phone's share sheet, and within one sync interval it shows up in Trilium with the article text Karakeep saved.

It's one small container that polls both REST APIs. It needs a Karakeep API key and a Trilium ETAPI token, and no public endpoint.

**Documentation: https://marceltov.github.io/karakeep-trilium-sync/**

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

- [Getting started](https://marceltov.github.io/karakeep-trilium-sync/getting-started/): from API keys to the first imported bookmark
- [Configuration](https://marceltov.github.io/karakeep-trilium-sync/configuration/): every setting, folders, labels and examples
- [Reddit](https://marceltov.github.io/karakeep-trilium-sync/reddit/): importing Reddit posts despite Reddit's login wall

## License

AGPL-3.0-or-later.
