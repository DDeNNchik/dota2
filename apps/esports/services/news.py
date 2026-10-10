"""Small, cached Dota 2 headline feed for the homepage."""

from html import unescape
from html.parser import HTMLParser
import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.core.cache import cache

NEWS_URL = 'https://www.gosugamers.net/dota2/articles'
NEWS_CACHE_KEY = 'homepage_dota2_news_v3'
NEWS_CACHE_SECONDS = 7 * 24 * 60 * 60
TRANSLATION_CACHE_SECONDS = 7 * 24 * 60 * 60
ENTITY_CACHE_KEY = 'homepage_dota2_news_entities_v1'
ENTITY_CACHE_SECONDS = 24 * 60 * 60

_DOTA_ENTITIES = (
    'The International', 'Team Spirit', 'Team Yandex', 'NAVI', 'Na`Vi', 'PGL Wallachia',
    'BLAST Slam', 'OG', 'Team Liquid', 'Tundra Esports', 'GosuGamers', 'Dota 2',
)
_CAPITALIZED_NAME = re.compile(
    r"\b(?:[A-Z][A-Za-z0-9’'’-]*|[A-Z]{2,})"
    r"(?:\s+(?:[A-Z][A-Za-z0-9’'’-]*|[A-Z]{2,}|of|the|and|&)){1,5}"
    r"(?:\s+\d+)?\b"
)
_ACRONYM = re.compile(r'\b[A-Z][A-Z0-9]{1,}\b')
def _known_dota_entities():
    """Get canonical team, player, and tournament names from the local catalog."""
    cached = cache.get(ENTITY_CACHE_KEY)
    if cached is not None:
        return cached

    names = list(_DOTA_ENTITIES)
    try:
        from apps.esports.models import ProPlayer, ProTeam, ProTeamMember, Tournament

        for model, fields in (
            (ProTeam, ('name', 'short_name')),
            (ProTeamMember, ('nickname', 'real_name')),
            (ProPlayer, ('leaderboard_name', 'team_tag', 'sponsor', 'real_name')),
            (Tournament, ('name', 'organizer')),
        ):
            for field in fields:
                names.extend(model.objects.values_list(field, flat=True).distinct())
    except Exception:
        # News translation should still work when the catalog database is unavailable.
        pass

    names = sorted({name.strip() for name in names if isinstance(name, str) and len(name.strip()) > 1}, key=len, reverse=True)
    cache.set(ENTITY_CACHE_KEY, names, ENTITY_CACHE_SECONDS)
    return names


def _protect_entities(text):
    """Replace likely proper names with tokens before machine translation."""
    candidates = []
    for name in _known_dota_entities():
        pattern = re.compile(rf'(?<!\w){re.escape(name)}(?!\w)', re.IGNORECASE)
        candidates.extend((match.start(), match.end(), match.group(0)) for match in pattern.finditer(text))
    candidates.extend((match.start(), match.end(), match.group(0)) for match in _CAPITALIZED_NAME.finditer(text))
    candidates.extend((match.start(), match.end(), match.group(0)) for match in _ACRONYM.finditer(text))
    candidates.sort(key=lambda item: (item[0], -(item[1] - item[0])))

    replacements = {}
    output = []
    cursor = 0
    token_index = 0
    for start, end, name in candidates:
        if start < cursor:
            continue
        token = f'XQZTERM{token_index}QZX'
        token_index += 1
        replacements[token] = name
        output.extend((text[cursor:start], token))
        cursor = end
    output.append(text[cursor:])
    return ''.join(output), replacements


def _restore_entities(text, replacements):
    for token, name in replacements.items():
        text = text.replace(token, name)
    return text


class _ArticleParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.articles = []
        self._anchor = None
        self._paragraph = None
        self._image = ''

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        href = attrs.get('href', '')
        if tag == 'a' and href.startswith('/dota2/news/') and self._anchor is None:
            self._anchor = {'url': f'https://www.gosugamers.net{href}', 'paragraphs': []}
        elif tag == 'p' and self._anchor is not None:
            self._paragraph = ''
        elif tag == 'img' and self._anchor is not None and not self._image:
            srcset = attrs.get('srcset', '')
            candidates = []
            for candidate in srcset.split(','):
                parts = candidate.strip().split()
                if parts and parts[0].startswith('https://static.gosugamers.net/'):
                    candidates.append(parts[0])
            self._image = candidates[-1] if candidates else attrs.get('src', '')

    def handle_data(self, data):
        if self._paragraph is not None:
            self._paragraph += data

    def handle_endtag(self, tag):
        if tag == 'p' and self._paragraph is not None and self._anchor is not None:
            text = ' '.join(self._paragraph.split())
            if text:
                self._anchor['paragraphs'].append(text)
            self._paragraph = None
        elif tag == 'a' and self._anchor is not None:
            paragraphs = self._anchor['paragraphs']
            if paragraphs:
                self.articles.append({
                    'title': paragraphs[0][:180],
                    'summary': paragraphs[1][:260] if len(paragraphs) > 1 else '',
                    'url': self._anchor['url'],
                    'image_url': self._image,
                })
            self._anchor = None
            self._paragraph = None
            self._image = ''


def _importance(article):
    title = article['title'].casefold()
    score = 0
    for words, points in (
        (('the international', ' ti ', 'world champion', 'champion', 'wins ', 'win '), 5),
        (('major', 'grand final', 'finals', 'tournament', 'qualify'), 3),
        (('transfer', 'joins ', 'join ', 'leaves ', 'signs ', 'roster', 'retires'), 2),
        (('patch', 'valve', 'update'), 1),
    ):
        if any(word in title for word in words):
            score += points
    return score


def fetch_homepage_news():
    """Return cached, source-linked headlines; refresh once every seven days."""
    cached = cache.get(NEWS_CACHE_KEY)
    if cached is not None:
        return cached

    request = Request(NEWS_URL, headers={
        'User-Agent': 'DotaForge/1.0 (Dota 2 community platform)',
        'Accept': 'text/html',
    })
    try:
        with urlopen(request, timeout=8) as response:
            page = response.read(2_000_000).decode('utf-8', 'replace')
    except (HTTPError, URLError, TimeoutError, OSError):
        cache.set(NEWS_CACHE_KEY, [], 60 * 60)
        return []

    parser = _ArticleParser()
    parser.feed(page)
    # The source page is newest-first. Within its recent items, prefer major
    # tournament outcomes and roster moves while keeping the feed varied.
    ranked = sorted(enumerate(parser.articles), key=lambda item: (-_importance(item[1]), item[0]))
    selected, seen = [], set()
    for _, article in ranked:
        if article['url'] in seen:
            continue
        seen.add(article['url'])
        selected.append(article)
        if len(selected) == 12:
            break

    cache.set(NEWS_CACHE_KEY, selected, NEWS_CACHE_SECONDS if selected else 60 * 60)
    return selected


def translate_homepage_news(articles, language):
    """Translate cached English headlines for Russian and Ukrainian readers."""
    target = {'ru': 'ru', 'uk': 'uk'}.get(language)
    if not target or not articles:
        return articles

    cache_key = f'homepage_dota2_news_translation_{target}_v3'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    translated_articles = []
    all_translated = True
    for article in articles:
        translated = dict(article)
        title = article.get('title', '')
        summary = article.get('summary', '')
        source_text = f'{title}\n{summary}' if summary else title
        protected_text, replacements = _protect_entities(source_text)
        request_url = 'https://api.mymemory.translated.net/get?' + urlencode({
            'q': protected_text,
            'langpair': f'en|{target}',
        })
        request = Request(request_url, headers={
            'User-Agent': 'DotaForge/1.0 (Dota 2 community platform)',
            'Accept': 'application/json',
        })
        try:
            with urlopen(request, timeout=5) as response:
                payload = json.loads(response.read().decode('utf-8'))
            result = unescape(payload.get('responseData', {}).get('translatedText', '')).strip()
            parts = result.split('\n', 1)
            # If the provider drops or alters a marker, keep the English source
            # rather than risking a translated team, player, or tournament name.
            tokens_intact = all(token in result for token in replacements)
            if payload.get('responseStatus') == 200 and parts[0] and tokens_intact:
                result = _restore_entities(result, replacements)
                parts = result.split('\n', 1)
                translated['title'] = parts[0]
                if summary and len(parts) == 2:
                    translated['summary'] = parts[1]
                elif summary:
                    all_translated = False
            else:
                all_translated = False
        except (HTTPError, URLError, TimeoutError, OSError, ValueError):
            all_translated = False
        translated_articles.append(translated)

    cache.set(cache_key, translated_articles, TRANSLATION_CACHE_SECONDS if all_translated else 60 * 60)
    return translated_articles
