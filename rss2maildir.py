#!/usr/bin/env python3
#
# Python script to convert from RSS to Maildir
#
# Copyright (C) 2015-2021  Jochen Sprickerhof
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import errno
import os
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from hashlib import sha256
from json import dump, load
from mailbox import (ExternalClashError, Maildir, MaildirMessage,
                     _create_carefully, _sync_close)
from os.path import expanduser, join
from subprocess import check_output
from time import gmtime, strftime, struct_time
from typing import Any, Callable

from feedparser import FeedParserDict, parse
from html2text import HTML2Text
from lxml.html.diff import htmldiff

import config


# fmt: off
class MyMaildir(Maildir):
    """Modified from /usr/lib/python3.6/mailbox.py"""

    def add(self, add):
        """Add message and return assigned key."""
        message = add[0]
        key = add[1]
        tmp_file = self._create_tmp(key)
        try:
            self._dump_message(message, tmp_file)
        except BaseException:
            tmp_file.close()
            os.remove(tmp_file.name)
            raise
        _sync_close(tmp_file)
        if isinstance(message, MaildirMessage):
            subdir = message.get_subdir()
            suffix = self.colon + message.get_info()
            if suffix == self.colon:
                suffix = ''
        else:
            subdir = 'new'
            suffix = ''
        uniq = os.path.basename(tmp_file.name).split(self.colon)[0]
        dest = os.path.join(self._path, subdir, uniq + suffix)
        if isinstance(message, MaildirMessage):
            os.utime(tmp_file.name,
                     (os.path.getatime(tmp_file.name), message.get_date()))
        # No file modification should be done after the file is moved to its
        # final position in order to prevent race conditions with changes
        # from other programs
        try:
            try:
                os.link(tmp_file.name, dest)
            except (AttributeError, PermissionError):
                os.rename(tmp_file.name, dest)
            else:
                os.remove(tmp_file.name)
        except OSError as e:
            os.remove(tmp_file.name)
            if e.errno == errno.EEXIST:
                raise ExternalClashError('Name clash with existing message: %s'
                                         % dest)
            else:
                raise
        return uniq

    def _create_tmp(self, key):
        """Create a file in the tmp subdirectory and open and return it."""
        path = os.path.join(self._path, 'tmp', key)
        try:
            os.stat(path)
        except FileNotFoundError:
            Maildir._count += 1
            try:
                return _create_carefully(path)
            except FileExistsError:
                pass

        # Fall through to here if stat succeeded or open raised EEXIST.
        raise ExternalClashError('Name clash prevented file creation: %s' %
                                 path)
# fmt: on


def replace_dict(string: str, dct: dict[str, str]) -> str:
    for key in dct:
        string = string.replace(key, dct[key])
    return string


def get_date(entry, feed: FeedParserDict, updated: struct_time) -> struct_time:
    if "updated_parsed" in entry:
        return entry.updated_parsed
    if "published_parsed" in entry:
        return entry.published_parsed
    if "updated_parsed" in feed.feed:
        return feed.feed.updated_parsed
    if "updated_parsed" in feed:
        return feed.updated_parsed
    return updated


def get_id(entry, use_uid: bool) -> str:
    if use_uid and "id" in entry:
        content = entry.id
    elif "summary" in entry and entry.summary:
        content = entry.summary
    elif "title" in entry and entry.title:
        content = entry.title
    else:
        content = entry.link

    return sha256(content.encode("utf-8")).hexdigest()


def pparse(feed_url: str, etag: str = None, modified: str = None) -> FeedParserDict:
    if feed_url.startswith("exec:"):
        process = check_output(expanduser(feed_url.removeprefix("exec:")), text=True)
        return parse(process, etag=etag, modified=modified)
    return parse(feed_url, etag=etag, modified=modified)


def main() -> None:
    box = MyMaildir(expanduser(config.maildir), factory=MaildirMessage)
    old_mails = list(box.keys())
    cache_new: dict[str, Any] = {}

    try:
        with open(
            join(expanduser(config.maildir), "cache.json"), encoding="utf-8"
        ) as json_cache:
            cache = load(json_cache)
    except IOError:
        cache = {}

    for feed_entry in config.feeds:
        feed_url = feed_entry["url"] if "url" in feed_entry else feed_entry
        filter_func: Callable = (
            feed_entry["filter"] if "filter" in feed_entry else lambda x: False
        )
        use_uid = feed_entry["use_uid"] if "use_uid" in feed_entry else False
        use_header = feed_entry["use_header"] if "use_header" in feed_entry else True
        use_date = feed_entry["use_date"] if "use_date" in feed_entry else True

        if use_header and feed_url in cache and "etag" in cache[feed_url]:
            feed = pparse(feed_url, etag=cache[feed_url]["etag"])
        elif use_header and feed_url in cache and "modified" in cache[feed_url]:
            feed = pparse(feed_url, modified=cache[feed_url]["modified"])
        else:
            feed = pparse(feed_url)

        cache_new[feed_url] = {}
        if use_header:
            if "etag" in feed:
                cache_new[feed_url]["etag"] = feed.etag
            elif "modified" in feed:
                cache_new[feed_url]["modified"] = feed.modified

        san_dict = {
            " ": "_",
            ".": "_",
            ":": "_",
            "/": "_",
        }
        file_title = feed_entry["title"] if "title" in feed_entry else feed_url
        file_title = replace_dict(file_title, san_dict)
        file_title = "".join([i if ord(i) < 128 else "_" for i in file_title])

        if len(feed.entries) == 0:
            old_mails = [m for m in old_mails if not m.startswith(file_title)]
            cache_new[feed_url]["entries"] = cache.get(feed_url, {}).get("entries", {})
            continue

        cache_new[feed_url]["entries"] = {}
        title = feed_entry["title"] if "title" in feed_entry else feed.feed.title
        now = gmtime()

        html2text = HTML2Text()
        html2text.inline_links = False
        html2text.unicode_snob = True
        html2text.wrap_links = False

        for entry in reversed(feed.entries):
            if filter_func(entry):
                continue
            summary = entry.summary if "summary" in entry else entry.link
            author = f"Author: {entry.author}<br>" if "author" in entry else ""
            content = f'<a href="{entry.link}">Link</a><br>{author}<br>{summary}'

            uid = entry.id if "id" in entry else entry.link

            cache_new[feed_url]["entries"][uid] = content

            old_content = cache.get(feed_url, {}).get("entries", {}).get(uid)

            if old_content and old_content != content:
                content = htmldiff(old_content, content)

            file_name = f"{file_title}.{get_id(entry, use_uid)}"
            date = get_date(entry, feed, now) if use_date else now
            if not date:
                date = now

            if file_name not in box:
                msg = MIMEMultipart("alternative")
                san_dict = {
                    "»": "",
                }
                msg["From"] = Header(formataddr((replace_dict(title, san_dict), "a@b")))
                msg["Date"] = strftime("%a, %d %b %Y %H:%M:%S %z", date)
                msg["Subject"] = Header(entry.title.replace("\n", ""), "UTF-8")
                msg.attach(MIMEText(html2text.handle(content), "plain", "UTF-8"))
                msg.attach(MIMEText(content, "html", "UTF-8"))
                box.add((msg, file_name))

            if file_name in old_mails:
                old_mails.remove(file_name)

    with open(
        join(expanduser(config.maildir), "cache.json"), "w", encoding="utf-8"
    ) as json_cache:
        dump(cache_new, json_cache, indent=2)

    for message in old_mails:
        if "F" not in box.get_message(message).get_flags():
            del box[message]


if __name__ == "__main__":
    main()
