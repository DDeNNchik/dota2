"""Importer for Liquipedia's public MediaWiki API."""

from datetime import date, datetime
from html.parser import HTMLParser
import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen

from django.utils.text import slugify


class LiquipediaError(RuntimeError):
    pass


class _TournamentTableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = []
        self._row = None
        self._cell = None
        self._anchor = None
        self._cell_depth = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'tr':
            self._row = []
        elif self._row is not None and tag == 'td':
            self._cell = {'class': attrs.get('class', ''), 'text': '', 'links': []}
            self._cell_depth = 1
        elif self._cell is not None:
            if tag in ('td', 'div', 'span', 'a'):
                self._cell_depth += 1
            if tag == 'a':
                self._anchor = {'href': attrs.get('href', ''), 'text': ''}

    def handle_endtag(self, tag):
        if self._cell is not None and tag == 'a' and self._anchor is not None:
            self._anchor['text'] = self._anchor['text'].strip()
            self._cell['links'].append(self._anchor)
            self._anchor = None
        if self._cell is not None and tag in ('td', 'div', 'span', 'a'):
            self._cell_depth -= 1
            if tag == 'td':
                self._cell['text'] = ' '.join(self._cell['text'].split())
                self._row.append(self._cell)
                self._cell = None
        if tag == 'tr' and self._row is not None:
            if self._row:
                self.rows.append(self._row)
            self._row = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell['text'] += data
            if self._anchor is not None:
                self._anchor['text'] += data


def _parse_date_range(value):
    """Parse the common Liquipedia table dates, e.g. 'Jan 20–31, 2027'."""
    value = ' '.join(value.replace('\xa0', ' ').split())
    for fmt in ('%b %d–%d, %Y', '%b %d-%d, %Y'):
        try:
            month, days_year = value.split(' ', 1)
            days, year = days_year.split(', ')
            first, last = days.replace('–', '-').split('-')
            start = datetime.strptime(f'{month} {int(first)} {year}', '%b %d %Y').date()
            end = datetime.strptime(f'{month} {int(last)} {year}', '%b %d %Y').date()
            return start, end
        except (ValueError, TypeError):
            continue
    for fmt in ('%b %d, %Y', '%d %b %Y'):
        try:
            parsed = datetime.strptime(value, fmt).date()
            return parsed, parsed
        except ValueError:
            pass
    return None, None


def fetch_tournaments(contact_email):
    params = urlencode({'action': 'parse', 'page': 'Portal:Tournaments', 'prop': 'text', 'format': 'json'})
    request = Request(
        f'https://liquipedia.net/dota2/api.php?{params}',
        headers={
            'User-Agent': f'DotaForge/1.0 (https://liquipedia.net/dota2/Portal:Tournaments; {contact_email})',
            'Accept-Encoding': 'gzip',
        },
    )
    try:
        with urlopen(request, timeout=25) as response:
            import gzip
            body = response.read()
            if response.headers.get('Content-Encoding') == 'gzip':
                body = gzip.decompress(body)
        payload = json.loads(body)
    except (HTTPError, URLError, TimeoutError, ValueError, OSError) as error:
        raise LiquipediaError('Liquipedia API request failed') from error
    html = (payload.get('parse') or {}).get('text', {}).get('*')
    if not html:
        raise LiquipediaError('Liquipedia returned no tournament list')
    parser = _TournamentTableParser()
    parser.feed(html)
    today = date.today()
    results, seen = [], set()
    for row in parser.rows:
        tournament_cell = next((cell for cell in row if 'tournament' in cell['class'].casefold()), None)
        tournament_link = next((
            link for link in (tournament_cell or {}).get('links', [])
            if link['href'].startswith('/dota2/') and link['text']
        ), None)
        if not tournament_link:
            continue
        # Ignore navigation/category links; tournament listings have a date and prize pool.
        texts = [cell['text'] for cell in row]
        date_text = next((text for text in texts if _parse_date_range(text)[0]), '')
        starts_at, ends_at = _parse_date_range(date_text)
        if not starts_at or not ends_at or ends_at < today:
            continue
        title = tournament_link['text'].strip()
        source_url = f"https://liquipedia.net{tournament_link['href']}"
        if source_url in seen:
            continue
        seen.add(source_url)
        prize_text = next((text for text in texts if '$' in text), '')
        try:
            prize_pool = int(''.join(character for character in prize_text.split('$', 1)[1] if character.isdigit()))
        except (IndexError, ValueError):
            prize_pool = 0
        participant_cell = next((cell for cell in row if 'participant' in cell['class'].casefold()), None)
        participants = []
        if participant_cell:
            participants = [link['text'] for link in participant_cell['links'] if link['text'] and link['text'].casefold() != 'tbd']
        results.append({
            'name': title[:150],
            'slug': slugify(tournament_link['href'].removeprefix('/dota2/'))[:50],
            'source_url': source_url,
            'starts_at': starts_at,
            'ends_at': ends_at,
            'prize_pool': prize_pool,
            'participants': participants,
        })
    return results


def fetch_tournament_details(records, contact_email):
    """Fetch tournament wikitext in one batched MediaWiki API request."""
    if not records:
        return {}
    titles = [unquote(urlparse(record['source_url']).path.removeprefix('/dota2/')).replace('_', ' ') for record in records]
    params = urlencode({
        'action': 'query', 'prop': 'revisions', 'rvprop': 'content', 'rvslots': 'main',
        'titles': '|'.join(titles), 'format': 'json', 'formatversion': '2',
    })
    request = Request(
        f'https://liquipedia.net/dota2/api.php?{params}',
        headers={
            'User-Agent': f'DotaForge/1.0 (https://liquipedia.net/dota2/Portal:Tournaments; {contact_email})',
            'Accept-Encoding': 'gzip',
        },
    )
    try:
        with urlopen(request, timeout=35) as response:
            import gzip
            body = response.read()
            if response.headers.get('Content-Encoding') == 'gzip':
                body = gzip.decompress(body)
        payload = json.loads(body)
    except (HTTPError, URLError, TimeoutError, ValueError, OSError) as error:
        raise LiquipediaError('Liquipedia tournament details request failed') from error

    results = {}
    for page in (payload.get('query') or {}).get('pages', []):
        revisions = page.get('revisions') or []
        if not revisions:
            continue
        content = (revisions[0].get('slots') or {}).get('main', {}).get('content', '')
        def infobox(name):
            found = re.search(rf'^\|{name}\s*=\s*([^\n|]+)', content, re.M)
            return found.group(1).strip() if found else ''

        participants = []
        section = re.search(r'==\s*Participants\s*==(?P<body>.*?)(?:\n==|\Z)', content, re.S | re.I)
        if section:
            participants = list(dict.fromkeys(
                match.strip() for match in re.findall(r'\{\{Opponent\|([^|\n{}]+)', section.group('body'))
                if match.strip() and match.strip().casefold() not in {'tbd', 'team tbd'}
            ))
        results[page.get('title', '')] = {
            'organizer': infobox('organizer'),
            'location': ', '.join(filter(None, (infobox('city'), infobox('country')))),
            'format': infobox('format').replace('<br>', ' · '),
            'participants': participants,
        }
    return results
