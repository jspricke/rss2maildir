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
    entry.summary = sub(r'<img [^>]*>', '', entry.summary)
    return False


feeds = [
    {'url': 'http://www.heise.de/newsticker/heise-atom.xml', 'title': 'Heise', 'use_uid': True},
    {'url': 'http://www.heise.de/open/news/news-atom.xml', 'title': 'Heise', 'use_uid': True},
    {'url': 'http://www.heise.de/security/news/news-atom.xml', 'title': 'Heise', 'use_uid': True},
    {'url': 'http://www.tagesschau.de/xml/rss2', 'filter': tagesschau, 'use_uid': True},
    {'url': 'https://blog.fefe.de/rss.xml?html', 'use_header': False},
    'http://git.suckless.org/dwm/atom',
    {'url': 'https://github.com/weechat/scripts/commits/master.atom', 'title': 'weechat scripts'},
]
