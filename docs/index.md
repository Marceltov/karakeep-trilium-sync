---
hide:
  - toc
---

<div class="ks-hero" markdown>

<div markdown>

# Your Karakeep bookmarks, as Trilium notes

<p class="ks-hero__lead">karakeep-trilium-sync copies the bookmarks you tag in Karakeep into Trilium, with the article text Karakeep saved. Save a page from the browser extension or your phone's share sheet, and it shows up in your notes a few minutes later.</p>

[Set it up](getting-started.md){ .md-button .md-button--primary } [Configuration](configuration.md){ .md-button }

</div>

<div class="ks-hero__mark"><img src="logo.svg" alt=""></div>

</div>

It's one small container next to Trilium:

```yaml
karakeep-trilium-sync:
  image: ghcr.io/marceltov/karakeep-trilium-sync:latest
  environment:
    KARAKEEP_API_ADDR: https://karakeep.example.com
    KARAKEEP_API_KEY: ${KARAKEEP_API_KEY}
    TRILIUM_SERVER_URL: http://trilium:8080
    TRILIUM_ETAPI_TOKEN: ${TRILIUM_ETAPI_TOKEN}
```

## What it does

- **Tag to import.** Tag a bookmark `trilium` in Karakeep, or put it in a list, and the next run turns it into a Trilium note. Afterwards the bookmark is tagged `trilium-imported`.
- **The text, not just the link.** Articles arrive as Karakeep extracted them, with author, publisher and publish date. PDFs and images bring their extracted text, and text bookmarks their text.
- **Goes where you want it.** Pick the parent note by ID or by a label search, sort notes into dated folders like `2026/10`, and add your own labels to every note.
- **Never imports twice.** Each note carries a `#karakeepId` label, so a bookmark is imported once even if a run fails halfway.
- **Reddit works.** Reddit shows crawlers a login page instead of the post, so the sync gets Reddit posts from Reddit's own feeds. See [Reddit](reddit.md).
- **Talks to the APIs only.** It polls Karakeep's REST API and writes through Trilium's ETAPI, so the three can run on different hosts. It needs no MCP, no OAuth and no public endpoint.

```mermaid
flowchart LR
  you@{ img: "icons/you.svg", label: "You<br>browser, phone", pos: "b", w: 48, h: 48, constraint: "on" }
  karakeep@{ img: "icons/karakeep.svg", label: "Karakeep", pos: "b", w: 48, h: 48, constraint: "on" }
  reddit@{ img: "icons/reddit.svg", label: "Reddit feeds", pos: "b", w: 48, h: 48, constraint: "on" }
  sync@{ img: "logo.svg", label: "karakeep-trilium-sync", pos: "b", w: 64, h: 64, constraint: "on" }
  trilium@{ img: "icons/trilium.svg", label: "Trilium", pos: "b", w: 48, h: 48, constraint: "on" }
  you -- "save + tag" --> karakeep
  karakeep -- "tagged bookmarks" --> sync
  reddit -. "Reddit posts" .-> sync
  sync -- "new notes" --> trilium
```

!!! tip "Keeping an LLM wiki in Trilium?"

    The sync can feed a wiki's raw sources: point it at the *Sources* note and sort by year, see [the example](configuration.md#an-llm-wikis-sources). The [LLM wiki skill](https://trilium-plugin.marceltov.de/skills/#knowledge-base) of [trilium-plugin](https://trilium-plugin.marceltov.de/) sets up such a wiki and ingests the imported sources into it.
