"""Importer for Liquipedia's public MediaWiki API."""

from datetime import date, datetime
from html.parser import HTMLParser
import json
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlencode, urlparse
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


class _TeamRankingParser(HTMLParser):
    """Extract ranked teams from Liquipedia's public rankings table."""

    def __init__(self):
        super().__init__()
        self.rows = []
        self._row = None
        self._cell = None
        self._anchor = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'tr':
            classes = attrs.get('class', '')
            if 'row--body' in classes and 'graph-row' not in classes:
                self._row = {}
        elif tag == 'td' and self._row is not None:
            key = attrs.get('data-ranking-table-cell')
            if key in {'rank', 'team', 'rating', 'region'}:
                self._cell = {'key': key, 'text': '', 'title': '', 'href': '', 'image': '', 'srcset': ''}
        elif self._cell is not None:
            if tag == 'a':
                self._anchor = attrs
            elif tag == 'img' and self._cell['key'] == 'team' and not self._cell['image']:
                self._cell['image'] = attrs.get('src', '')
                self._cell['srcset'] = attrs.get('srcset', '')

    def handle_endtag(self, tag):
        if tag == 'a' and self._anchor is not None and self._cell and self._cell['key'] == 'team':
            self._cell['title'] = self._anchor.get('title', '')
            self._cell['href'] = self._anchor.get('href', '')
            self._anchor = None
        elif tag == 'td' and self._cell is not None:
            key = self._cell.pop('key')
            self._row[key] = self._cell
            self._cell = None
        elif tag == 'tr' and self._row is not None:
            self.rows.append(self._row)
            self._row = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell['text'] += data


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


def fetch_team_rankings(contact_email, limit=100):
    """Fetch Liquipedia's current Dota 2 team ranking and logos."""
    params = urlencode({'action': 'parse', 'page': 'Portal:Rankings', 'prop': 'text', 'format': 'json'})
    request = Request(
        f'https://liquipedia.net/dota2/api.php?{params}',
        headers={
            'User-Agent': f'DotaForge/1.0 (https://liquipedia.net/dota2/Portal:Rankings; {contact_email})',
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
        raise LiquipediaError('Liquipedia team ranking request failed') from error

    html = (payload.get('parse') or {}).get('text', {}).get('*')
    if not html:
        raise LiquipediaError('Liquipedia returned no team ranking')
    parser = _TeamRankingParser()
    parser.feed(html)
    teams = []
    for row in parser.rows:
        try:
            rank = int(row.get('rank', {}).get('text', '').strip())
            rating = int(float(row.get('rating', {}).get('text', '').strip()))
        except (ValueError, TypeError):
            continue
        team_cell = row.get('team', {})
        name = (team_cell.get('title') or '').strip()
        page_path = team_cell.get('href', '')
        if not name or not page_path.startswith('/dota2/'):
            continue
        image = team_cell.get('image') or ''
        srcset = team_cell.get('srcset') or ''
        candidates = []
        for candidate in srcset.split(','):
            parts = candidate.strip().split()
            if len(parts) == 2 and parts[1].endswith('x'):
                try:
                    candidates.append((float(parts[1][:-1]), parts[0]))
                except ValueError:
                    pass
        if candidates:
            image = max(candidates)[1]
        if image.startswith('/'):
            image = f'https://liquipedia.net{image}'
        teams.append({
            'rank': rank,
            'name': name,
            'rating': rating,
            'region': row.get('region', {}).get('text', '').strip(),
            'source_url': f"https://liquipedia.net{page_path}",
            'logo_url': image,
        })
        if len(teams) >= limit:
            break
    if not teams:
        raise LiquipediaError('Liquipedia returned no parseable ranked teams')
    return teams


def fetch_tournament_details(records, contact_email):
    """Fetch tournament wikitext in one batched MediaWiki API request."""
    if not records:
        return {}
    time.sleep(2)
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


def _image_filename(value):
    """Extract a clean file title from an infobox value (comments often follow it)."""
    value = re.split(r'<!--|<br\s*/?>', value or '', maxsplit=1, flags=re.I)[0]
    value = re.sub(r'<[^>]+>', '', value).strip().replace('_', ' ')
    value = re.sub(r'^(?:File|Image)\s*:\s*', '', value, flags=re.I)
    return value.strip(' []')


def _fetch_image_urls(filenames, contact_email):
    """Resolve Liquipedia file titles to appropriately sized thumbnails."""
    filenames = list(dict.fromkeys(name for name in filenames if name))
    urls = {}
    for offset in range(0, len(filenames), 40):
        if offset:
            time.sleep(2)
        params = urlencode({
            'action': 'query', 'prop': 'imageinfo', 'iiprop': 'url', 'iiurlwidth': 480,
            'titles': '|'.join(f'File:{name}' for name in filenames[offset:offset + 40]),
            'format': 'json', 'formatversion': '2',
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
            raise LiquipediaError('Liquipedia image lookup request failed') from error
        for page in (payload.get('query') or {}).get('pages', []):
            imageinfo = page.get('imageinfo') or []
            if not imageinfo:
                continue
            image = imageinfo[0]
            url = image.get('thumburl') or image.get('url', '')
            file_title = page.get('title', '').partition(':')[2]
            if file_title and url:
                urls[file_title.casefold()] = url
    return urls


def _fetch_wikitext(titles, contact_email):
    """Retrieve pages in API-sized batches with Liquipedia's request spacing."""
    pages = []
    for offset in range(0, len(titles), 40):
        if offset:
            time.sleep(2)
        params = urlencode({
            'action': 'query', 'prop': 'revisions', 'rvprop': 'content', 'rvslots': 'main',
            'titles': '|'.join(titles[offset:offset + 40]), 'format': 'json', 'formatversion': '2',
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
            raise LiquipediaError('Liquipedia team or player page request failed') from error
        pages.extend((payload.get('query') or {}).get('pages', []))
    return pages


def fetch_team_profiles(teams, contact_email):
    """Read Liquipedia team logos and active rosters, then player portrait files."""
    teams = list(teams)
    if not teams:
        return {}
    time.sleep(2)
    pages = _fetch_wikitext([team.name for team in teams], contact_email)
    profiles = {}
    people = {}
    filenames = []
    for page in pages:
        revisions = page.get('revisions') or []
        if not revisions:
            continue
        content = (revisions[0].get('slots') or {}).get('main', {}).get('content', '')
        title = page.get('title', '')
        infobox = re.search(r'\{\{Infobox team(?P<body>.*?)^\}\}', content, re.S | re.M)
        logo = ''
        if infobox:
            match = re.search(r'^\|image\s*=\s*([^\n|]+)', infobox.group('body'), re.M)
            logo = _image_filename(match.group(1)) if match else ''
            if logo:
                filenames.append(logo)

        active = re.search(
            r'===\s*(?:Active(?: Roster)?)\s*===(?P<body>.*?)(?=^===|\Z)',
            content, re.S | re.M | re.I,
        )
        roster = []
        if active:
            for match in re.finditer(r'\{\{Person\|(?P<body>[^{}]*)\}\}', active.group('body')):
                fields = {}
                for item in match.group('body').split('|'):
                    if '=' in item:
                        key, value = item.split('=', 1)
                        fields[key.strip().casefold()] = value.strip()
                nickname = fields.get('id') or fields.get('name')
                if not nickname:
                    continue
                player_title = fields.get('link') or nickname
                person = {
                    'nickname': nickname[:128],
                    'real_name': fields.get('name', '')[:128],
                    'role': fields.get('position') or fields.get('role', ''),
                    'title': player_title,
                    'sort_order': int(fields.get('position', '0')) if fields.get('position', '').isdigit() else len(roster) + 1,
                }
                roster.append(person)
                people[player_title.casefold()] = person
        profiles[title] = {
            'logo_file': logo,
            'source_url': f"https://liquipedia.net/dota2/{quote(title.replace(' ', '_'), safe='/()_')}",
            'roster': roster,
        }

    player_titles = list(people)
    if player_titles:
        time.sleep(2)
        player_pages = _fetch_wikitext(player_titles, contact_email)
        for page in player_pages:
            revisions = page.get('revisions') or []
            if not revisions:
                continue
            content = (revisions[0].get('slots') or {}).get('main', {}).get('content', '')
            player_infobox = re.search(r'\{\{Infobox player(?P<body>.*?)^\}\}', content, re.S | re.M)
            if not player_infobox:
                continue
            match = re.search(r'^\|image\s*=\s*([^\n|]+)', player_infobox.group('body'), re.M)
            if not match:
                continue
            image = _image_filename(match.group(1))
            person = people.get(page.get('title', '').casefold())
            if person:
                person['photo_file'] = image
                if image:
                    filenames.append(image)

    if filenames:
        time.sleep(2)
    image_urls = _fetch_image_urls(filenames, contact_email) if filenames else {}
    for profile in profiles.values():
        profile['logo_url'] = image_urls.get(profile.pop('logo_file', '').casefold(), '')
        for person in profile['roster']:
            person['photo_url'] = image_urls.get(person.pop('photo_file', '').casefold(), '')

    return profiles
