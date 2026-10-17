import json
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import SimpleTestCase

from .services import news


class NewsFeedTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    @patch('apps.esports.services.news.urlopen')
    def test_fetch_parses_ranks_deduplicates_and_caches_articles(self, urlopen):
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = b'''<a href="/dota2/news/roster"><p>Team Spirit announces roster change</p><p>Collapse joins the team.</p><img src="https://static.gosugamers.net/a.jpg"></a>
        <a href="/dota2/news/ordinary"><p>Small update</p></a>
        <a href="/dota2/news/roster"><p>Duplicate article</p></a>'''
        urlopen.return_value = response

        articles = news.fetch_homepage_news()
        self.assertEqual([item['title'] for item in articles], [
            'Team Spirit announces roster change', 'Small update',
        ])
        self.assertEqual(articles[0]['summary'], 'Collapse joins the team.')
        self.assertEqual(articles[0]['image_url'], 'https://static.gosugamers.net/a.jpg')
        self.assertTrue(articles[0]['url'].startswith('https://www.gosugamers.net/'))
        self.assertEqual(news.fetch_homepage_news(), articles)
        urlopen.assert_called_once()

    @patch('apps.esports.services.news.urlopen', side_effect=TimeoutError)
    def test_fetch_caches_empty_result_after_provider_failure(self, urlopen):
        self.assertEqual(news.fetch_homepage_news(), [])
        self.assertEqual(news.fetch_homepage_news(), [])
        urlopen.assert_called_once()

    def test_translation_skips_english_and_uses_cached_translation(self):
        articles = [{'title': 'Team Spirit wins', 'summary': 'A major final.', 'url': '/news'}]
        self.assertIs(news.translate_homepage_news(articles, 'en'), articles)
        cache.set('homepage_dota2_news_translation_ru_v3', [{'title': 'Перевод'}])
        self.assertEqual(news.translate_homepage_news(articles, 'ru'), [{'title': 'Перевод'}])

    @patch('apps.esports.services.news._known_dota_entities', return_value=['Team Spirit'])
    @patch('apps.esports.services.news.urlopen')
    def test_translation_protects_proper_names_and_restores_them(self, urlopen, _entities):
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = json.dumps({
            'responseStatus': 200,
            'responseData': {'translatedText': 'Перевод XQZTERM0QZX\nОни выиграли.'},
        }).encode()
        urlopen.return_value = response
        articles = [{'title': 'Team Spirit wins', 'summary': 'They win.', 'url': '/news'}]

        translated = news.translate_homepage_news(articles, 'ru')

        self.assertEqual(translated[0]['title'], 'Перевод Team Spirit')
        self.assertEqual(translated[0]['summary'], 'Они выиграли.')

    @patch('apps.esports.services.news.urlopen')
    def test_translation_keeps_english_when_provider_drops_protected_name(self, urlopen):
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = json.dumps({
            'responseStatus': 200, 'responseData': {'translatedText': 'Перевод'},
        }).encode()
        urlopen.return_value = response
        article = {'title': 'The International begins', 'summary': 'Team Spirit attends.', 'url': '/news'}

        translated = news.translate_homepage_news([article], 'uk')

        self.assertEqual(translated[0]['title'], article['title'])
        self.assertEqual(translated[0]['summary'], article['summary'])
