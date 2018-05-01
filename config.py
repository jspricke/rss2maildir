#!/usr/bin/env python
#
# Python script to convert from RSS to Maildir (config file)
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

from re import sub

maildir = '.maildir/Feeds'


def tagesschau(entry):
    if 'sportschau' in entry.link:
        return True
    entry.summary = sub(r'<a href[^>]*><img [^>]*></a>', '', entry.summary)
    entry.summary = sub(r'<a href[^>]*>Meldung bei www.tagesschau.de lesen</a>', '', entry.summary)
    entry.summary = entry.summary.replace('<br /><br />', '')
    return False


def heise_open(entry):
    entry.id = sub(r'.*-([0-9]*).html', r'https://heise.de/-\1', entry.id)
    return False


def heise_security(entry):
    entry.id = sub(r'http://', 'https://', entry.id)
    return False


feeds = [
    {'url': 'https://www.heise.de/newsticker/heise-atom.xml', 'title': 'Heise', 'use_uid': True},
    {'url': 'https://www.heise.de/open/news/news-atom.xml', 'title': 'Heise', 'filter': heise_open, 'use_uid': True},
    {'url': 'https://www.heise.de/security/news/news-atom.xml', 'title': 'Heise', 'filter': heise_security, 'use_uid': True},
    {'url': 'https://www.tagesschau.de/xml/rss2', 'filter': tagesschau, 'use_uid': True},
    {'url': 'https://blog.fefe.de/rss.xml?html', 'use_header': False},
    {'url': 'https://github.com/jspricke/rss2maildir/commits/master.atom', 'title': 'rss2maildir'},
]
