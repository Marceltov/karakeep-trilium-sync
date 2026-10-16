"""karakeep_sync against in-memory fakes of the Karakeep and Trilium APIs."""

import json
from datetime import date

import httpx
import pytest

import karakeep_sync as ks

PARENT = "srcRoot"
YEAR = str(date.today().year)
MONTH = date.today().strftime("%m")


def link_bookmark(bid, **content):
    return {
        "id": bid,
        "title": None,
        "note": None,
        "tags": [{"id": "t-wiki", "name": "wiki", "attachedBy": "human"}],
        "createdAt": "2026-10-01T08:00:00.000Z",
        "content": {
            "type": "link",
            "url": f"https://example.com/{bid}",
            "title": f"Article {bid}",
            "crawlStatus": "success",
            "crawledAt": "2026-10-02T09:30:00.000Z",
            "htmlContent": f"<p>Body of {bid}</p>",
            **content,
        },
    }


class FakeKarakeep:
    def __init__(self, bookmarks, tags=("wiki",), feeds=(), lists=()):
        self.bookmarks = bookmarks
        self.feeds = list(feeds)
        self.tags = [{"id": f"t-{n}", "name": n} for n in tags]
        self.lists = [{"id": f"l-{n}", "name": n} for n in lists]
        self.attached = []

    def _page(self, request):
        if request.url.params.get("cursor") == "p2":
            return httpx.Response(200, json={"bookmarks": self.bookmarks[1:], "nextCursor": None})
        return httpx.Response(200, json={"bookmarks": self.bookmarks[:1], "nextCursor": "p2"})

    def handler(self, request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer kk-key"
        path = request.url.path.removeprefix("/api/v1")
        if path == "/tags":
            needle = request.url.params["nameContains"]
            return httpx.Response(200, json={
                "tags": [t for t in self.tags if needle in t["name"]], "nextCursor": None,
            })
        if path == "/lists":
            return httpx.Response(200, json={"lists": self.lists})
        if path == "/feeds":
            return httpx.Response(200, json={"feeds": self.feeds})
        if path in ("/tags/t-wiki/bookmarks", "/lists/l-reading/bookmarks"):
            return self._page(request)
        if request.method == "POST" and path.endswith("/tags"):
            bid = path.split("/")[2]
            self.attached.append((bid, json.loads(request.content)["tags"][0]["tagName"]))
            return httpx.Response(200, json={"attached": []})
        return httpx.Response(404)


class FakeTrilium:
    def __init__(self, with_year=True):
        self.notes = {
            "root": {"title": "root", "parent": None, "labels": [], "content": ""},
            PARENT: {"title": "Sources", "parent": "root", "labels": [("llmWikiPart", "sources")], "content": ""},
        }
        if with_year:
            self.notes["year1"] = {"title": YEAR, "parent": PARENT, "labels": [("wikiSourceGroup", YEAR)], "content": ""}
        self.counter = 0

    def _matches(self, query, labels):
        name, _, value = query.lstrip("#").partition("=")
        return (name, value.strip('"')) in labels

    def _ancestors(self, nid):
        while nid:
            yield nid
            nid = self.notes[nid]["parent"]

    def handler(self, request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "etapi-token"
        path = request.url.path.removeprefix("/etapi")
        if path == "/notes":
            under = request.url.params.get("ancestorNoteId")
            hits = [
                {"noteId": nid, "parentNoteIds": [n["parent"]]}
                for nid, n in self.notes.items()
                if self._matches(request.url.params["search"], n["labels"])
                and (under is None or under in list(self._ancestors(nid))[1:])
            ]
            return httpx.Response(200, json={"results": hits})
        if request.method == "GET" and path.startswith("/notes/"):
            nid = path.split("/")[2]
            if nid not in self.notes:
                return httpx.Response(404, json={"message": "not found"})
            children = [c for c, n in self.notes.items() if n["parent"] == nid]
            return httpx.Response(200, json={"noteId": nid, "title": self.notes[nid]["title"], "childNoteIds": children})
        body = json.loads(request.content)
        if path == "/create-note":
            self.counter += 1
            nid = f"new{self.counter}"
            self.notes[nid] = {"title": body["title"], "parent": body["parentNoteId"], "labels": [], "content": body["content"]}
            return httpx.Response(201, json={"note": {"noteId": nid}})
        if path == "/attributes":
            self.notes[body["noteId"]]["labels"].append((body["name"], body["value"]))
            return httpx.Response(201, json={})
        return httpx.Response(404)

    def created(self):
        return {nid: n for nid, n in self.notes.items() if nid.startswith("new")}

    def titled(self, title):
        return next(n for n in self.notes.values() if n["title"] == title)


WIKI = dict(
    tag="wiki", done_tag="wiki-imported", parent_search="#llmWikiPart=sources", folder="%Y",
    folder_labels='#wikiSourceGroup={name} #iconClass="bx bx-folder"',
)


def run(kk_fake, tr_fake, **overrides):
    cfg = ks.Config(**{**WIKI, **overrides})
    cfg.validate()
    kk = httpx.Client(base_url="http://kk/api/v1", headers={"Authorization": "Bearer kk-key"},
                      transport=httpx.MockTransport(kk_fake.handler))
    tr = httpx.Client(base_url="http://trilium/etapi", headers={"Authorization": "etapi-token"},
                      transport=httpx.MockTransport(tr_fake.handler))
    def no_network(url, follow_redirects):
        raise AssertionError(f"unexpected Reddit fetch: {url}")

    return ks.sync_once(kk, tr, cfg, no_network)


def test_imports_link_bookmarks_across_pages_into_year_folder():
    kk = FakeKarakeep([link_bookmark("b1"), link_bookmark("b2")])
    tr = FakeTrilium()
    assert run(kk, tr) == 2
    notes = tr.created()
    assert {n["title"] for n in notes.values()} == {"Article b1", "Article b2"}
    note = tr.titled("Article b1")
    assert note["parent"] == "year1"
    assert "<p>Body of b1</p>" in note["content"]
    assert 'href="https://example.com/b1"' in note["content"]
    assert ("karakeepId", "b1") in note["labels"]
    assert ("sourceUrl", "https://example.com/b1") in note["labels"]
    assert ("fetchedOn", "2026-10-02") in note["labels"]
    assert ("fetchedVia", "karakeep") in note["labels"]
    assert sorted(kk.attached) == [("b1", "wiki-imported"), ("b2", "wiki-imported")]


def test_rerun_is_idempotent():
    kk = FakeKarakeep([link_bookmark("b1")])
    tr = FakeTrilium()
    run(kk, tr)
    kk.attached.clear()
    assert run(kk, tr) == 0
    assert len(tr.created()) == 1
    # Already in Trilium but not yet tagged in Karakeep: tag it, don't duplicate.
    assert kk.attached == [("b1", "wiki-imported")]


def test_skips_bookmarks_already_tagged_done():
    bm = link_bookmark("b1")
    bm["tags"].append({"id": "t-done", "name": "wiki-imported", "attachedBy": "human"})
    kk = FakeKarakeep([bm])
    tr = FakeTrilium()
    assert run(kk, tr) == 0
    assert kk.attached == []


def test_empty_done_tag_tags_nothing_and_still_imports_once():
    kk = FakeKarakeep([link_bookmark("b1")])
    tr = FakeTrilium()
    assert run(kk, tr, done_tag="") == 1
    assert run(kk, tr, done_tag="") == 0
    assert kk.attached == []


def test_pending_crawl_waits_for_next_run():
    kk = FakeKarakeep([link_bookmark("b1", crawlStatus="pending", htmlContent=None)])
    tr = FakeTrilium()
    assert run(kk, tr) == 0
    assert kk.attached == []


def test_failed_crawl_becomes_link_only_note():
    kk = FakeKarakeep([link_bookmark("b1", crawlStatus="failure", htmlContent=None)])
    tr = FakeTrilium()
    assert run(kk, tr) == 1
    (note,) = tr.created().values()
    assert 'href="https://example.com/b1"' in note["content"]
    assert not any(name == "fetchedVia" for name, _ in note["labels"])


def test_creates_folder_with_its_labels_when_missing():
    kk = FakeKarakeep([link_bookmark("b1")])
    tr = FakeTrilium(with_year=False)
    run(kk, tr)
    folder = tr.titled(YEAR)
    assert folder["parent"] == PARENT
    assert folder["labels"] == [("wikiSourceGroup", YEAR), ("iconClass", "bx bx-folder")]
    assert tr.notes[tr.titled("Article b1")["parent"]] is folder


def test_nested_folder_path_reuses_existing_levels():
    kk = FakeKarakeep([link_bookmark("b1"), link_bookmark("b2")])
    tr = FakeTrilium()
    run(kk, tr, folder="%Y/%m", folder_labels="")
    months = [nid for nid, n in tr.created().items() if n["title"] == MONTH]
    assert len(months) == 1 and tr.notes[months[0]]["parent"] == "year1"
    assert tr.titled("Article b2")["parent"] == months[0]


def test_defaults_put_notes_under_root_without_folders():
    kk = FakeKarakeep([link_bookmark("b1")])
    tr = FakeTrilium()
    run(kk, tr, parent_search="", folder="")
    assert tr.titled("Article b1")["parent"] == "root"


def test_parent_note_id_and_extra_labels():
    kk = FakeKarakeep([link_bookmark("b1")])
    tr = FakeTrilium()
    run(kk, tr, parent_search="", parent_note=PARENT, folder="", note_labels='#unread #from="karakeep app"')
    note = tr.titled("Article b1")
    assert note["parent"] == PARENT
    assert note["labels"][-2:] == [("unread", ""), ("from", "karakeep app")]


def test_unknown_parent_note_fails_the_run():
    kk = FakeKarakeep([link_bookmark("b1")])
    with pytest.raises(httpx.HTTPStatusError):
        run(kk, FakeTrilium(), parent_search="", parent_note="typo")


def test_imports_from_a_list_instead_of_a_tag():
    kk = FakeKarakeep([link_bookmark("b1")], tags=(), lists=("reading",))
    tr = FakeTrilium()
    assert run(kk, tr, list_name="reading") == 1


def test_missing_tag_is_a_no_op():
    kk = FakeKarakeep([link_bookmark("b1")], tags=("other",))
    tr = FakeTrilium()
    assert run(kk, tr) == 0
    assert tr.created() == {}


def test_parent_search_must_be_unique():
    tr = FakeTrilium()
    tr.notes["dup"] = {"title": "Sources 2", "parent": "root", "labels": [("llmWikiPart", "sources")], "content": ""}
    kk = FakeKarakeep([link_bookmark("b1")])
    with pytest.raises(RuntimeError, match="found 2"):
        run(kk, tr)


def test_config_from_env(monkeypatch):
    for k, v in {
        "KARAKEEP_API_ADDR": "https://kk.example/", "KARAKEEP_API_KEY": "k",
        "TRILIUM_ETAPI_TOKEN": "t", "TRILIUM_SERVER_URL": "http://tr:8080",
        "TRILIUM_FOLDER": "/%Y/", "REDDIT_FEEDS": "false", "SYNC_INTERVAL": "0",
    }.items():
        monkeypatch.setenv(k, v)
    cfg = ks.Config.from_env()
    assert cfg.karakeep_addr == "https://kk.example"
    assert cfg.etapi_url == "http://tr:8080/etapi"
    assert (cfg.tag, cfg.done_tag, cfg.parent_note) == ("trilium", "trilium-imported", "root")
    assert cfg.folder == "%Y" and cfg.reddit is False and cfg.interval == 0


@pytest.mark.parametrize("env", [
    {"KARAKEEP_API_KEY": ""}, {"TRILIUM_NOTE_LABELS": "unread"}, {"REDDIT_FEEDS": "maybe"},
])
def test_bad_config_is_rejected(monkeypatch, env):
    base = {"KARAKEEP_API_ADDR": "https://kk", "KARAKEEP_API_KEY": "k", "TRILIUM_ETAPI_TOKEN": "t"}
    for k, v in {**base, **env}.items():
        monkeypatch.setenv(k, v)
    with pytest.raises(ValueError):
        ks.Config.from_env()


def test_text_bookmark_is_escaped():
    bm = {"id": "t1", "title": None, "note": "why I saved it", "tags": [],
          "content": {"type": "text", "text": "First line <b>\n\nSecond para"}}
    title, content, labels = ks.render_note(bm)
    assert title == "First line <b>"
    assert "&lt;b&gt;" in content and "<p>Second para</p>" in content
    assert "why I saved it" in content
    assert labels == [("karakeepId", "t1")]


def test_asset_bookmark_uses_extracted_text():
    bm = {"id": "a1", "title": None, "note": None, "tags": [], "createdAt": "2026-09-01T00:00:00Z",
          "content": {"type": "asset", "assetType": "pdf", "assetId": "x", "fileName": "paper.pdf",
                      "content": "Extracted text"}}
    title, content, labels = ks.render_note(bm)
    assert title == "paper.pdf"
    assert "<p>Extracted text</p>" in content
    assert ("fetchedOn", "2026-09-01") in labels


def test_unknown_content_type_skipped():
    assert ks.render_note({"id": "u1", "content": {"type": "unknown"}}) is None


def test_reddit_disabled_keeps_karakeeps_capture():
    bm = link_bookmark("r1", url="https://www.reddit.com/r/x/comments/abc/t/")
    _, content, labels = ks.render_note(bm, None)
    assert "Body of r1" in content and ("fetchedVia", "karakeep") in labels


REDDIT_FEED = """<?xml version="1.0" encoding="UTF-8"?><feed xmlns="http://www.w3.org/2005/Atom">
<title>A post : selfhosted</title>
<entry><author><name>/u/op</name></author><link href="https://www.reddit.com/r/selfhosted/comments/abc123/a_post/"/><content type="html">&lt;div class="md"&gt;&lt;p&gt;Post body&lt;/p&gt;&lt;/div&gt;</content></entry>
<entry><author><name>/u/commenter</name></author><link href="https://www.reddit.com/r/selfhosted/comments/abc123/a_post/c1/"/><content type="html">&lt;p&gt;Nice &amp;amp; useful&lt;/p&gt;</content></entry>
</feed>"""
SAVED_FEED = """<?xml version="1.0" encoding="UTF-8"?><feed xmlns="http://www.w3.org/2005/Atom">
<entry><author><name>/u/op</name></author><link href="https://www.reddit.com/r/selfhosted/comments/abc123/a_post/"/><content type="html">&lt;p&gt;Saved body&lt;/p&gt;</content></entry>
<entry><author><name>/u/other</name></author><link href="https://www.reddit.com/r/homelab/comments/zzz999/other/"/><content type="html">&lt;p&gt;Other&lt;/p&gt;</content></entry>
</feed>"""
SAVED_URL = "https://www.reddit.com/saved.rss?feed=secret&user=me"
POST_URL = "https://www.reddit.com/r/selfhosted/comments/abc123/a_post/"


def reddit_source(handler, feeds=()):
    kk = FakeKarakeep([], feeds=feeds)
    kk_client = httpx.Client(base_url="http://kk/api/v1", headers={"Authorization": "Bearer kk-key"},
                             transport=httpx.MockTransport(kk.handler))
    def fetch(url, follow_redirects):
        resp = handler(httpx.Request("GET", url))
        if follow_redirects and resp.status_code in (301, 302):
            resp = handler(httpx.Request("GET", resp.headers["location"]))
        return resp.status_code, resp.text, {
            "location": resp.headers.get("location", ""),
            "x-ratelimit-reset": resp.headers.get("x-ratelimit-reset", ""),
        }

    return ks.RedditSource(kk_client, fetch)


def reddit_bookmark(url=POST_URL):
    return link_bookmark("r1", url=url, title="A post", author="Log In", publisher="Log In",
                         htmlContent="<p>Let us know your cookie preferences</p>")


def test_reddit_post_comes_from_saved_feed_first():
    seen = []

    def handler(request):
        seen.append(str(request.url))
        return httpx.Response(200, text=SAVED_FEED)

    source = reddit_source(handler, feeds=[{"id": "f1", "name": "Reddit", "url": SAVED_URL, "enabled": True}])
    title, content, labels = ks.render_note(reddit_bookmark(), source)
    assert seen == [SAVED_URL]
    assert "cookie preferences" not in content and "Log In" not in content
    assert "<h2>Post by /u/op</h2><p>Saved body</p>" in content
    assert ("fetchedVia", "reddit-feed") in labels
    # The saved feed is fetched once per run, however many posts use it.
    ks.render_note(reddit_bookmark("https://www.reddit.com/r/homelab/comments/zzz999/other/"), source)
    assert seen == [SAVED_URL]


def test_non_reddit_feeds_are_ignored():
    def handler(request):
        assert str(request.url) == POST_URL + ".rss"
        return httpx.Response(200, text=REDDIT_FEED)

    source = reddit_source(handler, feeds=[{"id": "f2", "name": "HN", "url": "https://hnrss.org/newest", "enabled": True}])
    _, content, _ = ks.render_note(reddit_bookmark(), source)
    assert "Post body" in content


def test_post_missing_from_saved_feed_uses_its_own_feed_with_comments():
    def handler(request):
        if str(request.url) == SAVED_URL:
            return httpx.Response(200, text=SAVED_FEED.replace("abc123", "nothere"))
        assert str(request.url) == POST_URL + ".rss"
        return httpx.Response(200, text=REDDIT_FEED)

    source = reddit_source(handler, feeds=[{"id": "f1", "name": "Reddit", "url": SAVED_URL, "enabled": True}])
    _, content, labels = ks.render_note(reddit_bookmark(), source)
    assert '<h2>Post by /u/op</h2><div class="md"><p>Post body</p></div>' in content
    assert "<h3>/u/commenter</h3><p>Nice &amp; useful</p>" in content
    assert ("fetchedVia", "reddit-post-feed") in labels


def test_reddit_share_link_is_resolved_first():
    def handler(request):
        if "/s/" in request.url.path:
            return httpx.Response(301, headers={"location": POST_URL + "?share_id=x&utm_source=share"})
        assert str(request.url) == POST_URL + ".rss"
        return httpx.Response(200, text=REDDIT_FEED)

    _, content, _ = ks.render_note(
        reddit_bookmark("https://www.reddit.com/r/selfhosted/s/clJwh8lJvL"), reddit_source(handler))
    assert "Post body" in content


def test_reddit_refusal_waits_for_next_run():
    source = reddit_source(lambda request: httpx.Response(403, text="blocked"),
                           feeds=[{"id": "f1", "name": "Reddit", "url": SAVED_URL, "enabled": True}])
    assert ks.render_note(reddit_bookmark(), source) is None


def test_reddit_rate_limit_is_retried_once(monkeypatch):
    monkeypatch.setattr(ks.time, "sleep", lambda s: None)
    calls = []

    def handler(request):
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(429, headers={"x-ratelimit-reset": "5"})
        return httpx.Response(200, text=REDDIT_FEED)

    _, content, _ = ks.render_note(reddit_bookmark(), reddit_source(handler))
    assert len(calls) == 2 and "Post body" in content
