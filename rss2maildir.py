#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Python script to convert from RSS to Maildir
#
# Copyright (C) 2015  Jochen Sprickerhof
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
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from feedparser import parse
from hashlib import sha256
from mailbox import Maildir, _create_carefully, _sync_close, MaildirMessage, ExternalClashError
from os.path import join, isfile
from subprocess import Popen, PIPE
from time import gmtime, mktime, strftime

from config import *

import sys
import os
import errno
import warnings
with warnings.catch_warnings():
    if sys.py3kwarning:
        warnings.filterwarnings("ignore", ".*rfc822 has been removed",
                                DeprecationWarning)


class MyMaildir(Maildir):
    """Modified from /usr/lib/python2.7/mailbox.py"""

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
            if hasattr(os, 'link'):
                os.link(tmp_file.name, dest)
                os.remove(tmp_file.name)
            else:
                os.rename(tmp_file.name, dest)
        except OSError, e:
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
        except OSError, e:
            if e.errno == errno.ENOENT:
                Maildir._count += 1
                try:
                    return _create_carefully(path)
                except OSError, e:
                    if e.errno != errno.EEXIST:
                        raise
            else:
                raise

        # Fall through to here if stat succeeded or open raised EEXIST.
        raise ExternalClashError('Name clash prevented file creation: %s' %
                                 path)


def replace_dict(string, dict):
    for key in dict:
        string = string.replace(key, dict[key])
    return string


def get_date(entry, feed, updated):
    if 'updated_parsed' in entry.keys():
        return entry.updated_parsed
    if 'published_parsed' in entry:
        return entry.published_parsed
    if 'updated_parsed' in feed.feed:
        return feed.feed.updated_parsed
    if 'updated_parsed' in feed:
        return feed.updated_parsed
    return updated


def mail(title, entry, date):
    msg = MIMEMultipart('alternative')
    san_dict = {
        u'»': '',
    }
    msg['From'] = Header(formataddr((replace_dict(title, san_dict), '')), 'utf-8')
    msg['Date'] = strftime('%a, %d %b %Y %H:%M:%S %z', date)
    msg['Subject'] = Header(entry.title, 'utf-8')
    summary = entry.summary if 'summary' in entry else entry.link
    author = 'Author: %s<br>' % entry.author if 'author' in entry else ''
    html = '<a href="%s">Link</a><br>%s<br>%s' % (entry.link, author, summary)
    msg.attach(MIMEText(html, 'html', 'utf-8'))
    return msg


def pparse(feed_url, etag=None, modified=None):
    if feed_url.startswith('exec:'):
        return parse(Popen(feed_url[5:], stdout=PIPE, shell=True).communicate()[0], etag=etag, modified=modified)
    else:
        return parse(feed_url, etag=etag, modified=modified)


def main():
    now = gmtime()
    box = MyMaildir(maildir)
    for feed_entry in feeds:
        feed_url = feed_entry['url'] if 'url' in feed_entry else feed_entry
        filter_func = feed_entry['filter'] if 'filter' in feed_entry else lambda x: False
        use_uid = feed_entry['use_uid'] if 'use_uid' in feed_entry else False
        use_header = feed_entry['use_header'] if 'use_header' in feed_entry else True
        use_date = feed_entry['use_date'] if 'use_date' in feed_entry else True

        last_file = join(maildir, sha256(feed_url).hexdigest())
        if use_header and isfile(last_file):
            last = open(last_file).read()
            if last.startswith('E'):
                feed = pparse(feed_url, etag=last[2:])
            else:
                feed = pparse(feed_url, modified=last[2:])
        else:
            feed = pparse(feed_url)

        if len(feed.entries) == 0:
            continue

        if use_header:
            if 'etag' in feed:
                open(last_file, 'w').write('E %s' % feed.etag)
            elif 'modified' in feed:
                open(last_file, 'w').write('M %s' % feed.modified)

        title = feed_entry['title'] if 'title' in feed_entry else feed.feed.title

        san_dict = {
            ' ': '_',
            '.': '_',
            ':': '_',
            '/': '_',
        }
        file_title = replace_dict(title, san_dict)
        file_title = ''.join([i if ord(i) < 128 else '_' for i in file_title])

        for entry in reversed(feed.entries):
            if use_uid:
                content = entry.id if 'id' in entry else entry.link
            else:
                content = entry.summary.encode('utf-8') if 'summary' in entry else entry.link

            key = '%s.%s' % (file_title, sha256(content).hexdigest())
            date = get_date(entry, feed, now) if use_date else now

            if key not in box and not filter_func(entry) and mktime(now) - mktime(date) < 60*60*24*7:
                box.add((mail(title, entry, date), key))

if __name__ == '__main__':
    main()
