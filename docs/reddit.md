# Reddit

Reddit shows crawlers, Karakeep's included, a cookie and login page instead of the post, so Karakeep's capture of a Reddit post is useless. With `REDDIT_FEEDS` on (the default), the sync ignores that capture and takes the post from Reddit itself:

1. **From your private Reddit feeds** that Karakeep subscribes to, such as your saved posts. Their key lets them through, and each entry carries the post's text. They hold your most recent saves (about 25), without comments. Labelled `#fetchedVia=reddit-feed`.
2. **Otherwise from the post's own public feed**, which adds the comments but allows only about one anonymous request a minute. Labelled `#fetchedVia=reddit-post-feed`. Share links from the app (`/r/…/s/…`) are resolved to the post first.

If Reddit refuses both, the bookmark waits for the next run. Link posts carry only the link, so open or fetch the linked article yourself.

!!! note "Why curl"

    Reddit answers Python's HTTP client with *403 Blocked*, even with identical headers, because of its TLS fingerprint, but serves curl. The image ships curl and uses it for Reddit only.

## Import everything you save on Reddit

Your saved-posts feed works best, and Karakeep can also import from it:

1. On [reddit.com/prefs/feeds](https://www.reddit.com/prefs/feeds/), copy the RSS link of your *saved links*. It looks like `https://www.reddit.com/saved.rss?feed=…&user=…`. Treat it like a password.
2. In Karakeep, open *Settings → RSS Subscriptions* and add that URL. Karakeep now creates a bookmark for each post you save on Reddit.
3. In Karakeep's rule engine, under *Settings*, add a rule: when a bookmark is added and it was imported from that feed, add the tag `trilium` (your `KARAKEEP_TAG`).

Every post you save on Reddit then ends up in Trilium, with its text. Posts you share to Karakeep from the Reddit app work too, but come from the post's public feed with its rate limit.

The sync finds these feeds by listing your Karakeep RSS subscriptions; any enabled subscription on `reddit.com` counts. It fetches them once per run, and only when a Reddit bookmark is waiting.

## Turning it off

Set `REDDIT_FEEDS: "false"` to treat Reddit like any other site and keep Karakeep's capture. The sync then makes no requests to Reddit.
