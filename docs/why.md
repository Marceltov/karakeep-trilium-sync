# Why I built this

I keep an [LLM wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) in my self-hosted Trilium. Claude writes and maintains it: it reads raw sources, such as articles, posts and notes, and turns them into linked pages about the concepts, tools and people in them. A wiki like that is only as good as what goes in, so I needed a way to feed it that I'd actually use.

I already collect almost everything in Karakeep. The browser extension and the phone's share sheet take one tap, and Karakeep saves the page's text on its own. So Karakeep had to become the wiki's inbox.

## Why not Karakeep's MCP server

Karakeep has an MCP server, so the obvious idea was to let Claude read Karakeep directly. But that server only runs as a local process started by the MCP client. It has no HTTP endpoint and no OAuth login, so Claude on my phone and on claude.ai can't reach it. My Trilium, on the other hand, is reachable from all of them through [trilium-mcp](https://trilium-mcp.marceltov.de/).

So instead of connecting Claude to Karakeep, this sync copies the bookmarks into Trilium. Then the wiki needs only one connection, and every source sits in Trilium, next to the pages built from it.

## My setup

```mermaid
flowchart LR
  you@{ img: "../icons/you.svg", label: "Me<br>browser, phone", pos: "b", w: 48, h: 48, constraint: "on" }
  reddit@{ img: "../icons/reddit.svg", label: "Reddit saves", pos: "b", w: 48, h: 48, constraint: "on" }
  karakeep@{ img: "../icons/karakeep.svg", label: "Karakeep", pos: "b", w: 48, h: 48, constraint: "on" }
  sync@{ img: "../logo.svg", label: "karakeep-trilium-sync", pos: "b", w: 64, h: 64, constraint: "on" }
  trilium@{ img: "../icons/trilium.svg", label: "Trilium<br>Sources / 2026", pos: "b", w: 48, h: 48, constraint: "on" }
  mcp@{ img: "../icons/mcp.svg", label: "trilium-mcp", pos: "b", w: 48, h: 48, constraint: "on" }
  claude@{ img: "../icons/claude.svg", label: "Claude<br>with trilium-plugin", pos: "b", w: 48, h: 48, constraint: "on" }
  you -- "save + tag" --> karakeep
  reddit -. "RSS + rule" .-> karakeep
  karakeep -- "tagged bookmarks" --> sync
  sync -- "source notes" --> trilium
  claude -- "ingest" --> mcp
  mcp --> trilium
```

- **Trilium** runs in Docker at home, with the wiki in my own instance. Its rulebook is a schema note, and its raw material lives under *Sources*, in one folder per year.
- **trilium-mcp** runs next to Trilium and makes it reachable for Claude: from Claude Code with an ETAPI token, and from the Claude apps and claude.ai with an OAuth login.
- **Karakeep** runs as its own service. The sync reaches it over its HTTPS address.
- **karakeep-trilium-sync** runs in the same compose project as Trilium, every 15 minutes, configured like the [LLM wiki example](configuration.md#an-llm-wikis-sources).
- **Claude** has [trilium-plugin](https://trilium-plugin.marceltov.de/) installed, whose [LLM wiki skill](https://trilium-plugin.marceltov.de/skills/#knowledge-base) knows how to ingest sources, answer questions from the wiki and lint it.

## From a bookmark to a wiki page

1. **Collect.** When something is worth keeping, I save it to Karakeep and tag it `trilium`: in the browser with the extension, on the phone through the share sheet. Posts I save on Reddit need no extra step: Karakeep follows my private saved-posts feed, and a rule tags every post from it `trilium` ([how](reddit.md#import-everything-you-save-on-reddit)).
2. **Sync.** Within 15 minutes the sync turns the bookmark into a source note under *Sources/2026*, with the article text and the labels `#sourceUrl`, `#fetchedOn` and `#fetchedVia`. In Karakeep the bookmark is now tagged `trilium-imported`.
3. **Ingest.** To process them, I tell Claude "ingest the new sources". The skill reads the schema note, works through the sources it hasn't ingested yet and writes or updates the summary, concept and entity pages. New pages start as drafts marked AI-assisted, and the sources themselves stay untouched.
4. **Use.** Instead of searching my bookmarks, I can ask the wiki, e.g. "what do I know about VLANs?", and Claude answers from its pages.

Some saves don't carry their text. Paywalls, cookie banners and login walls give Karakeep nothing useful, and link posts only point elsewhere. Those become link-only sources, and the ingest fetches the page itself.
