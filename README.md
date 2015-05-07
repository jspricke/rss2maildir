# Python library to convert from RSS to Maildir

## Configuration

- Adopt maildir and feeds in rss2maildir.py.
- Setup cronjobs:

```
*/30 * * * * rss2maildir.py
25 3 * * * find ~/.maildir/Feeds/cur/ -ctime +7 -name "*,S" -delete
```
