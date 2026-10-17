from datetime import date
from textwrap import dedent
import json
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from .services import liquipedia


class LiquipediaParserTests(SimpleTestCase):
    def api_response(self, payload):
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = json.dumps(payload).encode()
        response.headers.get.return_value = None
        return response

    def test_parse_date_range_supports_ranges_single_dates_and_invalid_values(self):
        self.assertEqual(
            liquipedia._parse_date_range('Jan 20–31, 2027'),
            (date(2027, 1, 20), date(2027, 1, 31)),
        )
        self.assertEqual(
            liquipedia._parse_date_range('20 Jan 2027'),
            (date(2027, 1, 20), date(2027, 1, 20)),
        )
        self.assertEqual(liquipedia._parse_date_range('not a date'), (None, None))

    @patch('apps.esports.services.liquipedia.date')
    @patch('apps.esports.services.liquipedia.urlopen')
    def test_fetch_tournaments_extracts_future_event_and_ignores_old_or_invalid_rows(self, urlopen, date_mock):
        today = date(2027, 1, 1)
        date_mock.today.return_value = today
        # Avoid invoking the patched date constructor from the parser itself.
        with patch('apps.esports.services.liquipedia.datetime') as datetime_mock:
            from datetime import datetime as RealDateTime
            datetime_mock.strptime.side_effect = RealDateTime.strptime
            payload = {'parse': {'text': {'*': dedent('''
                <table><tr><td class="tournament-tier"><a href="/dota2/PGL_Wallachia_9">PGL Wallachia 9</a></td>
                <td>Jan 20–31, 2027</td><td>$1,250,000</td>
                <td class="participant"><a>Team Spirit</a><a>TBD</a><a>Team Yandex</a></td></tr>
                <tr><td class="tournament"><a href="/dota2/Old">Old Event</a></td><td>Jan 1, 2020</td></tr>
                <tr><td class="tournament"><a href="/dota2/NoDate">No Date</a></td><td>TBA</td></tr></table>''')}}}
            urlopen.return_value = self.api_response(payload)
            records = liquipedia.fetch_tournaments('dev@example.test')

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]['name'], 'PGL Wallachia 9')
        self.assertEqual(records[0]['slug'], 'pgl_wallachia_9')
        self.assertEqual(records[0]['prize_pool'], 1250000)
        self.assertEqual(records[0]['participants'], ['Team Spirit', 'Team Yandex'])
        self.assertEqual(records[0]['starts_at'], date(2027, 1, 20))
        self.assertIn('dev@example.test', urlopen.call_args.args[0].get_header('User-agent'))

    @patch('apps.esports.services.liquipedia.urlopen')
    def test_fetch_team_rankings_selects_best_logo_variant_and_respects_limit(self, urlopen):
        payload = {'parse': {'text': {'*': dedent('''
            <table>
              <tr class="row--body"><td data-ranking-table-cell="rank">1</td>
                <td data-ranking-table-cell="team"><a title="Team Alpha" href="/dota2/Team_Alpha">Alpha</a>
                  <img src="/small.png" srcset="/small.png 1x, /large.png 2x"></td>
                <td data-ranking-table-cell="rating">1234.8</td><td data-ranking-table-cell="region">Europe</td></tr>
              <tr class="row--body graph-row"><td data-ranking-table-cell="rank">2</td></tr>
              <tr class="row--body"><td data-ranking-table-cell="rank">bad</td></tr>
              <tr class="row--body"><td data-ranking-table-cell="rank">2</td>
                <td data-ranking-table-cell="team"><a title="Team Beta" href="/dota2/Team_Beta">Beta</a></td>
                <td data-ranking-table-cell="rating">900</td></tr>
            </table>''')}}}
        urlopen.return_value = self.api_response(payload)

        teams = liquipedia.fetch_team_rankings('dev@example.test', limit=1)

        self.assertEqual(teams, [{
            'rank': 1, 'name': 'Team Alpha', 'rating': 1234, 'region': 'Europe',
            'source_url': 'https://liquipedia.net/dota2/Team_Alpha',
            'logo_url': 'https://liquipedia.net/large.png',
        }])

    @patch('apps.esports.services.liquipedia.time.sleep')
    @patch('apps.esports.services.liquipedia.urlopen')
    def test_fetch_tournament_details_parses_infobox_and_deduplicates_participants(self, urlopen, _sleep):
        payload = {'query': {'pages': [{
            'title': 'Event One', 'revisions': [{'slots': {'main': {'content': '''
|organizer = PGL
|city = Bucharest
|country = Romania
|format = Group Stage<br>Playoffs
                == Participants ==
                {{Opponent|Team Spirit|x}}
                {{Opponent|TBD}}
                {{Opponent|Team Spirit}}
                {{Opponent|Team Yandex}}
                == Results ==
                '''}}}],
        }]}}
        urlopen.return_value = self.api_response(payload)

        details = liquipedia.fetch_tournament_details([
            {'source_url': 'https://liquipedia.net/dota2/Event_One'},
        ], 'dev@example.test')

        self.assertEqual(details['Event One'], {
            'organizer': 'PGL', 'location': 'Bucharest, Romania',
            'format': 'Group Stage · Playoffs', 'participants': ['Team Spirit', 'Team Yandex'],
        })

    def test_image_filename_removes_namespace_comments_and_markup(self):
        self.assertEqual(liquipedia._image_filename('File:Team_Logo.png<br>caption'), 'Team Logo.png')
