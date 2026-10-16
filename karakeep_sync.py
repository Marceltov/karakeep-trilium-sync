# SPDX-License-Identifier: AGPL-3.0-or-later
#
# karakeep-trilium-sync — copy Karakeep bookmarks into Trilium notes.
# Copyright (C) 2026 Marcel Bruckner
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU Affero General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License along
# with this program. If not, see <https://www.gnu.org/licenses/>.

"""Copy Karakeep bookmarks into Trilium as notes.

Every bookmark carrying KARAKEEP_TAG (or in KARAKEEP_LIST) becomes one text
note under the configured parent note, optionally in dated subfolders, holding
the article text Karakeep already crawled. The bookmark then gets
KARAKEEP_DONE_TAG. A #karakeepId label on the note makes a rerun idempotent even
if tagging the bookmark failed. All configuration is environment variables; see
Config.from_env and the README.
"""

import html
import logging
import os
import re
import shlex
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime

import httpx

log = logging.getLogger("karakeep_sync")

PAGE_SIZE = 50

# Reddit serves crawlers a cookie/login wall (also for .json and old.reddit), so
# Karakeep's capture of a Reddit post is useless. The post's Atom feed still
# answers anonymously, with the post body and its comments.
REDDIT_POST = re.compile(r"^https?://(?:[a-z]+\.)?reddit\.com/r/[^/]+/(?:comments|s)/", re.I)
REDDIT_USER_AGENT = "karakeep-trilium-sync/1.0 (personal notes importer)"
ATOM = "{http://www.w3.org/2005/Atom}"


# ---- Configuration ----

def parse_labels(spec: str) -> list[tuple[str, str]]:
    """'#a #b=c #d="e f"' -> [("a", ""), ("b", "c"), ("d", "e f")], Trilium's syntax."""
    labels = []
    for token in shlex.split(spec):
        if not token.startswith("#") or len(token) < 2:
            raise ValueError(f"label {token!r} must look like #name or #name=value")
        name, _, value = token[1:].partition("=")
        labels.append((name, value))
    return labels


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name, "").strip().lower()
    if not value:
        return default
    if value in ("1", "true", "yes", "on"):
        return True
    if value in ("0", "false", "no", "off"):
        return False
    raise ValueError(f"{name} must be true or false, not {value!r}")


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"{name} is not set")
    return value


@dataclass
class Config:
    karakeep_addr: str = ""
    karakeep_key: str = ""
    tag: str = "trilium"                  # bookmarks with this tag are imported...
    list_name: str = ""                   # ...or, if set, the bookmarks in this list
    done_tag: str = "trilium-imported"    # set once imported; "" = don't tag
    trilium_url: str = "http://trilium:8080"
    trilium_token: str = ""
    parent_note: str = "root"             # note id the notes go under...
    parent_search: str = ""               # ...or the one note this search finds
    folder: str = ""                      # strftime path below the parent, e.g. %Y or %Y/%m
    folder_labels: str = ""               # labels for new folders; {name} = folder title
    note_labels: str = ""                 # extra labels on every imported note
    reddit: bool = True                   # fetch Reddit posts from Reddit's feeds
    interval: int = 900                   # seconds between runs; 0 = run once

    @classmethod
    def from_env(cls) -> "Config":
        env = os.environ.get
        cfg = cls(
            karakeep_addr=_required_env("KARAKEEP_API_ADDR").rstrip("/"),
            karakeep_key=_required_env("KARAKEEP_API_KEY"),
            tag=env("KARAKEEP_TAG", cls.tag),
            list_name=env("KARAKEEP_LIST", ""),
            done_tag=env("KARAKEEP_DONE_TAG", cls.done_tag),
            trilium_url=env("TRILIUM_SERVER_URL", cls.trilium_url),
            trilium_token=_required_env("TRILIUM_ETAPI_TOKEN"),
            parent_note=env("TRILIUM_PARENT_NOTE", "") or cls.parent_note,
            parent_search=env("TRILIUM_PARENT_SEARCH", ""),
            folder=env("TRILIUM_FOLDER", "").strip("/"),
            folder_labels=env("TRILIUM_FOLDER_LABELS", ""),
            note_labels=env("TRILIUM_NOTE_LABELS", ""),
            reddit=_env_bool("REDDIT_FEEDS", True),
            interval=int(env("SYNC_INTERVAL", cls.interval)),
        )
        cfg.validate()
        return cfg

    def validate(self) -> None:
        if not self.list_name and not self.tag:
            raise ValueError("set KARAKEEP_TAG or KARAKEEP_LIST")
        parse_labels(self.note_labels)
        parse_labels(self.folder_labels.replace("{name}", "x"))

    @property
    def etapi_url(self) -> str:
        url = self.trilium_url.rstrip("/")
        return url if url.endswith("/etapi") else f"{url}/etapi"


def karakeep_client(cfg: Config) -> httpx.Client:
    return httpx.Client(
        base_url=f"{cfg.karakeep_addr}/api/v1",
        headers={"Authorization": f"Bearer {cfg.karakeep_key}"},
        timeout=30,
    )


def trilium_client(cfg: Config) -> httpx.Client:
    return httpx.Client(
        base_url=cfg.etapi_url, headers={"Authorization": cfg.trilium_token}, timeout=30
    )


# ---- Karakeep side ----

def _paged(kk: httpx.Client, path: str, key: str, params: dict):
    cursor = None
    while True:
        page = kk.get(path, params={**params, **({"cursor": cursor} if cursor else {})})
        page = page.raise_for_status().json()
        yield from page[key]
        cursor = page.get("nextCursor")
        if not cursor:
            return


def find_tag_id(kk: httpx.Client, name: str) -> str | None:
    for tag in _paged(kk, "/tags", "tags", {"nameContains": name}):
        if tag["name"] == name:
            return tag["id"]
    return None


def find_list_id(kk: httpx.Client, name: str) -> str | None:
    lists = kk.get("/lists").raise_for_status().json()["lists"]
    return next((lst["id"] for lst in lists if lst["name"] == name), None)


def pending_bookmarks(kk: httpx.Client, cfg: Config):
    """The bookmarks to import, or None if the tag/list doesn't exist yet."""
    if cfg.list_name:
        list_id = find_list_id(kk, cfg.list_name)
        path = list_id and f"/lists/{list_id}/bookmarks"
    else:
        tag_id = find_tag_id(kk, cfg.tag)
        path = tag_id and f"/tags/{tag_id}/bookmarks"
    if not path:
        return None
    return _paged(kk, path, "bookmarks", {"includeContent": "true", "limit": PAGE_SIZE})


def mark_done(kk: httpx.Client, bookmark_id: str, done_tag: str) -> None:
    if not done_tag:
        return
    kk.post(
        f"/bookmarks/{bookmark_id}/tags", json={"tags": [{"tagName": done_tag}]}
    ).raise_for_status()


# ---- Reddit ----

class RedditError(Exception):
    pass


# (url, follow_redirects) -> (status, body, {"location", "x-ratelimit-reset"})
Fetch = Callable[[str, bool], tuple[int, str, dict[str, str]]]


def curl_fetch(url: str, follow_redirects: bool = True) -> tuple[int, str, dict[str, str]]:
    """GET via curl. Reddit answers Python's TLS client with "403 Blocked" even
    with curl's exact headers, but serves curl, which the image ships."""
    if not url.startswith(("https://", "http://")):
        raise RedditError("not an http(s) URL")
    cmd = [
        "curl", "-sS", "--max-time", "30", "-A", REDDIT_USER_AGENT,
        "-w", "\n%{http_code}\t%{redirect_url}\t%header{x-ratelimit-reset}",
    ]
    if follow_redirects:
        cmd.append("-L")
    try:
        out = subprocess.run(cmd + ["--url", url], capture_output=True, check=True, timeout=40)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise RedditError(f"curl failed: {exc}") from None  # no URL: feed URLs carry a key
    body, _, trailer = out.stdout.decode("utf-8", "replace").rpartition("\n")
    code, location, reset = (trailer.split("\t") + ["", ""])[:3]
    return int(code), body, {"location": location, "x-ratelimit-reset": reset}


REDDIT_POST_ID = re.compile(r"/comments/([a-z0-9]+)", re.I)


def _post_id(url: str) -> str | None:
    match = REDDIT_POST_ID.search(url)
    return match.group(1).lower() if match else None


def _entries(feed_xml: str) -> list[tuple[str, str, str]]:
    """(link, author, content html) for each entry of a Reddit Atom feed."""
    return [
        (
            (entry.find(f"{ATOM}link").get("href") if entry.find(f"{ATOM}link") is not None else ""),
            entry.findtext(f"{ATOM}author/{ATOM}name") or "[deleted]",
            entry.findtext(f"{ATOM}content") or "",
        )
        for entry in ET.fromstring(feed_xml).findall(f"{ATOM}entry")
    ]


def _post_html(author: str, body: str) -> str:
    return f"<h2>Post by {html.escape(author)}</h2>{body}"


def _render_post_feed(feed_xml: str) -> str:
    entries = _entries(feed_xml)
    if not entries:
        raise ValueError("Reddit feed has no entries")
    (_, author, body), comments = entries[0], entries[1:]
    parts = [_post_html(author, body)]
    if comments:
        parts.append("<h2>Comments</h2>")
        parts += [f"<h3>{html.escape(a)}</h3>{b}" for _, a, b in comments]
    return "".join(parts)


class RedditSource:
    """Gets Reddit posts' text without hitting Reddit's crawler login wall.

    First choice: the user's private Reddit feeds that Karakeep subscribes to
    (e.g. saved.rss?feed=<key>). Their URLs carry the feed key, so Reddit serves
    them, and each entry holds the post body. They are fetched once per run, and
    only if a Reddit bookmark is being imported. Fallback for posts not in those
    feeds (older saves, links shared from the app): the post's own .rss, which
    adds comments but has a tiny anonymous rate limit.
    """

    def __init__(self, kk: httpx.Client, fetch: Fetch = curl_fetch):
        self.kk = kk
        self.fetch = fetch
        self._feed_posts: dict[str, str] | None = None

    def _get(self, url: str) -> str:
        status, body, headers = self.fetch(url, True)
        if status == 429:  # small per-IP budget that resets within a minute
            time.sleep(min(int(headers.get("x-ratelimit-reset") or 30), 60) + 1)
            status, body, headers = self.fetch(url, True)
        if status != 200:
            raise RedditError(f"HTTP {status}")
        return body

    def feed_posts(self) -> dict[str, str]:
        if self._feed_posts is None:
            self._feed_posts = {}
            try:
                feeds = self.kk.get("/feeds").raise_for_status().json()["feeds"]
            except httpx.HTTPError as exc:
                log.warning("could not list Karakeep feeds: %s", exc)
                feeds = []
            for feed in feeds:
                if not feed.get("enabled", True) or "reddit.com" not in feed["url"]:
                    continue
                try:
                    for link, author, body in _entries(self._get(feed["url"])):
                        if (post_id := _post_id(link)) and body:
                            self._feed_posts[post_id] = _post_html(author, body)
                except (RedditError, ET.ParseError) as exc:
                    log.warning("Reddit feed %r unavailable: %s", feed.get("name"), exc)
        return self._feed_posts

    def capture(self, url: str) -> tuple[str, str] | None:
        """(html, fetchedVia) for a post, or None if Reddit refused."""
        if (post_id := _post_id(url)) and post_id in self.feed_posts():
            return self.feed_posts()[post_id], "reddit-feed"
        try:
            if "/s/" in url:  # app share link: resolve to the canonical post URL
                status, _, headers = self.fetch(url, False)
                url = headers.get("location", "")
                if not REDDIT_POST.match(url):
                    raise RedditError(f"share link did not resolve to a post: HTTP {status}")
                if (post_id := _post_id(url)) and post_id in self.feed_posts():
                    return self.feed_posts()[post_id], "reddit-feed"
            feed_url = url.split("?")[0].rstrip("/") + "/.rss"
            return _render_post_feed(self._get(feed_url)), "reddit-post-feed"
        except (RedditError, ET.ParseError, ValueError) as exc:
            log.warning("Reddit post %s unavailable: %s", url, exc)
            return None


# ---- Bookmark -> note ----

def _day(timestamp: str | None) -> str:
    if not timestamp:
        return date.today().isoformat()
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00")).date().isoformat()


def _paragraphs(text: str) -> str:
    blocks = [b.strip() for b in text.replace("\r\n", "\n").split("\n\n") if b.strip()]
    return "".join(
        f"<p>{html.escape(b).replace(chr(10), '<br>')}</p>" for b in blocks
    )


def _link(url: str) -> str:
    u = html.escape(url, quote=True)
    return f'<a href="{u}">{html.escape(url)}</a>'


def render_note(
    bookmark: dict, reddit: RedditSource | None = None
) -> tuple[str, str, list[tuple[str, str]]] | None:
    """(title, html, labels) for a bookmark, or None if it isn't ready yet.

    A link whose crawl is still pending is retried on the next run. A link whose
    crawl produced no article becomes a note holding just the link. A Reddit
    post is taken from Reddit's feeds (see RedditSource) instead of Karakeep's
    capture, which is a login wall; if Reddit refuses, the bookmark waits for
    the next run.
    """
    content = bookmark.get("content") or {}
    kind = content.get("type")
    labels = [("karakeepId", bookmark["id"])]
    header = []
    if bookmark.get("note"):
        header.append(
            f"<blockquote><p><strong>Note from the bookmark:</strong></p>"
            f"{_paragraphs(bookmark['note'])}</blockquote>"
        )

    if kind == "link":
        if content.get("crawlStatus") == "pending":
            return None
        url = content["url"]
        title = bookmark.get("title") or content.get("title") or url
        labels.append(("sourceUrl", url))
        meta = [f"Source: {_link(url)}"]
        for key, label in (("author", "Author"), ("publisher", "Publisher")):
            if content.get(key):
                meta.append(f"{label}: {html.escape(content[key])}")
        if content.get("datePublished"):
            meta.append(f"Published: {_day(content['datePublished'])}")
        if REDDIT_POST.match(url) and reddit is not None:
            header.append(f"<p>{'<br>'.join(meta[:1])}</p>")  # Karakeep's author/publisher are the login wall's
            captured = reddit.capture(url)
            if captured is None:
                return None
            article, via = captured
            labels += [("fetchedOn", date.today().isoformat()), ("fetchedVia", via)]
            return title, "".join(header) + "<hr>" + article, labels
        header.append(f"<p>{'<br>'.join(meta)}</p>")
        article = content.get("htmlContent")
        if article:
            labels += [
                ("fetchedOn", _day(content.get("crawledAt"))),
                ("fetchedVia", "karakeep"),
            ]
            return title, "".join(header) + "<hr>" + article, labels
        return title, "".join(header), labels

    if kind == "text":
        text = content.get("text") or ""
        title = bookmark.get("title") or text.strip().split("\n", 1)[0][:80] or "Karakeep note"
        if content.get("sourceUrl"):
            labels.append(("sourceUrl", content["sourceUrl"]))
            header.append(f"<p>Source: {_link(content['sourceUrl'])}</p>")
        return title, "".join(header) + _paragraphs(text), labels

    if kind == "asset":
        title = bookmark.get("title") or content.get("fileName") or "Karakeep asset"
        if content.get("sourceUrl"):
            labels.append(("sourceUrl", content["sourceUrl"]))
            header.append(f"<p>Source: {_link(content['sourceUrl'])}</p>")
        name = html.escape(content.get("fileName") or content.get("assetType") or "file")
        header.append(f"<p>Extracted text of {name} (the file itself stays in Karakeep).</p>")
        labels += [("fetchedOn", _day(bookmark.get("createdAt"))), ("fetchedVia", "karakeep")]
        return title, "".join(header) + "<hr>" + _paragraphs(content.get("content") or ""), labels

    log.warning("bookmark %s has unsupported content type %r; skipped", bookmark["id"], kind)
    return None


# ---- Trilium side ----

def search(tr: httpx.Client, query: str, **params) -> list[dict]:
    resp = tr.get("/notes", params={"search": query, **params}).raise_for_status()
    return resp.json()["results"]


def resolve_parent(tr: httpx.Client, cfg: Config) -> str:
    if not cfg.parent_search:
        tr.get(f"/notes/{cfg.parent_note}").raise_for_status()  # fail early on a typo
        return cfg.parent_note
    found = search(tr, cfg.parent_search)
    if len(found) != 1:
        raise RuntimeError(
            f"TRILIUM_PARENT_SEARCH {cfg.parent_search!r} must find one note, found {len(found)}"
        )
    return found[0]["noteId"]


def add_label(tr: httpx.Client, note_id: str, name: str, value: str = "") -> None:
    tr.post(
        "/attributes", json={"noteId": note_id, "type": "label", "name": name, "value": value}
    ).raise_for_status()


def create_note(tr: httpx.Client, parent_id: str, title: str, content: str) -> str:
    resp = tr.post(
        "/create-note",
        json={"parentNoteId": parent_id, "title": title, "type": "text", "content": content},
    ).raise_for_status()
    return resp.json()["note"]["noteId"]


class Folders:
    """Finds or creates the TRILIUM_FOLDER path (e.g. 2026/10) below the parent.

    A folder is an existing child note with the folder's title; a missing one is
    created and given TRILIUM_FOLDER_LABELS. Lookups are cached for one run.
    """

    def __init__(self, tr: httpx.Client, cfg: Config, parent_id: str):
        self.tr, self.cfg, self.parent_id = tr, cfg, parent_id
        self._cache: dict[tuple[str, str], str] = {}

    def _child(self, parent_id: str, title: str) -> str:
        key = (parent_id, title)
        if key not in self._cache:
            parent = self.tr.get(f"/notes/{parent_id}").raise_for_status().json()
            for child_id in parent["childNoteIds"]:
                child = self.tr.get(f"/notes/{child_id}").raise_for_status().json()
                self._cache[(parent_id, child["title"])] = child_id
        if key not in self._cache:
            note_id = create_note(self.tr, parent_id, title, "")
            labels = self.cfg.folder_labels.replace("{name}", title)
            for name, value in parse_labels(labels):
                add_label(self.tr, note_id, name, value)
            log.info("created folder %s (%s)", title, note_id)
            self._cache[key] = note_id
        return self._cache[key]

    def for_today(self) -> str:
        note_id = self.parent_id
        if self.cfg.folder:
            for title in date.today().strftime(self.cfg.folder).split("/"):
                note_id = self._child(note_id, title)
        return note_id


def already_imported(tr: httpx.Client, parent_id: str, bookmark_id: str) -> bool:
    return bool(search(tr, f'#karakeepId="{bookmark_id}"', ancestorNoteId=parent_id))


# ---- One run ----

def sync_once(
    kk: httpx.Client, tr: httpx.Client, cfg: Config, reddit_fetch: Fetch = curl_fetch
) -> int:
    """Import every pending bookmark; return how many notes were created."""
    bookmarks = pending_bookmarks(kk, cfg)
    if bookmarks is None:
        what = f"list {cfg.list_name!r}" if cfg.list_name else f"tag {cfg.tag!r}"
        log.info("no Karakeep %s yet; nothing to import", what)
        return 0
    parent_id = resolve_parent(tr, cfg)
    folders = Folders(tr, cfg, parent_id)
    reddit = RedditSource(kk, reddit_fetch) if cfg.reddit else None
    extra_labels = parse_labels(cfg.note_labels)
    created = 0
    for bookmark in bookmarks:
        if cfg.done_tag and any(t["name"] == cfg.done_tag for t in bookmark.get("tags", [])):
            continue
        if already_imported(tr, parent_id, bookmark["id"]):
            mark_done(kk, bookmark["id"], cfg.done_tag)
            continue
        rendered = render_note(bookmark, reddit)
        if rendered is None:
            continue
        title, content, labels = rendered
        note_id = create_note(tr, folders.for_today(), title, content)
        for name, value in labels + extra_labels:
            add_label(tr, note_id, name, value)
        mark_done(kk, bookmark["id"], cfg.done_tag)
        created += 1
        log.info("imported %r as %s", title, note_id)
    return created


def main() -> None:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)  # one line per request is noise
    try:
        cfg = Config.from_env()
    except ValueError as exc:
        log.error("invalid configuration: %s", exc)
        sys.exit(2)
    with karakeep_client(cfg) as kk, trilium_client(cfg) as tr:
        while True:
            try:
                count = sync_once(kk, tr, cfg)
                log.info("run finished: %d new note(s)", count)
            except (httpx.HTTPError, RuntimeError) as exc:
                log.error("run failed: %s", exc)
                if cfg.interval == 0:
                    sys.exit(1)
            if cfg.interval == 0:
                return
            time.sleep(cfg.interval)


if __name__ == "__main__":
    main()
