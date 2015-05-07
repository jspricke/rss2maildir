#!/usr/bin/env python
#
# Combine multiple Heise RSS feeds
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

from urllib import urlopen
from xml.etree.ElementTree import parse, ParseError
from re import search, sub
from sys import stdout


def main():
    try:
        tree = parse(urlopen('http://www.heise.de/open/news/news.rdf'))
    except (IOError, ParseError):
        return
    root = tree.find('channel')
    ids = set()

    for entry in tree.findall('channel/item'):
        entry_id = entry.findtext('link')
        entry_id = entry_id.replace('0E', '-')
        entry_id = entry_id.replace('0B', '.')
        e_id2s = search('-([0-9A-F]*).html', entry_id).groups()[0]
        e_id2 = int(sub('[A-F]', '', e_id2s))
        ids.add(e_id2)

    try:
        ntree = parse(urlopen('http://www.heise.de/security/news/news.rdf'))
    except (IOError, ParseError):
        return

    for entry in ntree.findall('channel/item'):
        entry_id = entry.findtext('link')
        entry_id = entry_id.replace('0E', '-')
        entry_id = entry_id.replace('0B', '.')
        e_id2s = search('-([0-9A-F]*).html', entry_id).groups()[0]
        e_id2 = int(sub('[A-F]', '', e_id2s))
        if e_id2 not in ids:
            root.append(entry)
            ids.add(e_id2)

    try:
        ntree = parse(urlopen('http://www.heise.de/newsticker/heise.rdf'))
    except (IOError, ParseError):
        return

    for entry in ntree.findall('channel/item'):
        entry_id = entry.findtext('link')
        e_id2s = search('-([0-9A-F]*).html', entry_id).groups()[0]
        e_id2 = int(sub('[A-F]', '', e_id2s))
        if e_id2 not in ids:
            root.append(entry)
            ids.add(e_id2)

    tree.write(stdout)

if __name__ == '__main__':
    main()
