# What gets imported

Each bookmark becomes one text note, titled with the bookmark's title (or the page title, or the URL).

| Bookmark | Note content | Labels |
|---|---|---|
| Link, crawled | Source link, author, publisher and publish date, then the article as Karakeep extracted it | `#karakeepId`, `#sourceUrl`, `#fetchedOn` (crawl date), `#fetchedVia=karakeep` |
| Link, crawl failed | Just the source link | `#karakeepId`, `#sourceUrl` |
| Link, still crawling | Nothing yet; retried on the next run | |
| Reddit post | The post from Reddit's feeds, see [Reddit](reddit.md) | `#karakeepId`, `#sourceUrl`, `#fetchedOn`, `#fetchedVia=reddit-feed` or `reddit-post-feed` |
| Text | The text, as paragraphs | `#karakeepId`, `#sourceUrl` if set |
| PDF or image | The text Karakeep extracted; the file stays in Karakeep | `#karakeepId`, `#sourceUrl` if set, `#fetchedOn`, `#fetchedVia=karakeep` |

The bookmark's own note, if you wrote one, is quoted at the top. Images in the article stay links to their original URLs; nothing is downloaded into Trilium. Your `TRILIUM_NOTE_LABELS` are added after these labels.

Highlights and Karakeep's AI tags and summaries aren't copied.

## Each bookmark once

After importing, the sync tags the bookmark `KARAKEEP_DONE_TAG` and skips it from then on.

Independently of that tag, a bookmark that already has a note with its `#karakeepId` below the parent is never imported again. If a run fails after creating the note but before tagging the bookmark, the next run only adds the tag. The same holds with an empty done tag.

To import a bookmark again, delete its note in Trilium, then remove the done tag in Karakeep.

## Timing

Each run goes through every bookmark with the tag (or in the list) and imports everything pending, however much that is. A new note goes into the folder for the day it's *imported*, not the day it was bookmarked.
