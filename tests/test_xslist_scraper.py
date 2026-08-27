import unittest

from xslist_scraper import XslistSession, parse_xslist_details


class FakeResponse:
    def __init__(self, url, body):
        self.url = url
        self.body = body


class FakeStealthySession:
    def __init__(self, responses, **kwargs):
        self.responses = list(responses)
        self.kwargs = kwargs
        self.enter_count = 0
        self.exit_count = 0
        self.fetch_calls = []

    def __enter__(self):
        self.enter_count += 1
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.exit_count += 1

    def fetch(self, url):
        self.fetch_calls.append(url)
        return self.responses.pop(0)


class XslistSessionTests(unittest.TestCase):
    def test_parses_current_xslist_detail_structure(self):
        html = """
        <html><body><main><section><p>
          出生: 1993年08月15日<br>
          三围: B84 / W59 / H88<br>
          罩杯: E Cup<br>
          身高: <span itemprop="height">159cm</span><br>
          国籍: <span itemprop="nationality">日本</span><br>
          血型: n/a<br>
        </p></section></main></body></html>
        """

        details = parse_xslist_details(html)

        self.assertEqual(details["出生"], "1993年08月15日")
        self.assertEqual(details["三围"], "B84 / W59 / H88")
        self.assertEqual(details["罩杯"], "E Cup")
        self.assertEqual(details["身高"], "159cm")
        self.assertEqual(details["国籍"], "日本")
        self.assertNotIn("血型", details)

    def test_returns_empty_details_when_current_container_is_missing(self):
        self.assertEqual(parse_xslist_details("<html><body>missing</body></html>"), {})

    def test_reuses_one_cloudflare_session(self):
        created_sessions = []
        responses = [
            FakeResponse("https://xslist.org/search", b"<html>search</html>"),
            FakeResponse("https://xslist.org/person/1", "<html>detail</html>"),
        ]

        def session_factory(**kwargs):
            session = FakeStealthySession(responses, **kwargs)
            created_sessions.append(session)
            return session

        xslist = XslistSession(proxy="http://127.0.0.1:7890", session_factory=session_factory)

        first_url, first_body = xslist.fetch("https://xslist.org/search?query=test")
        second_url, second_body = xslist.fetch("https://xslist.org/person/1")

        self.assertEqual(len(created_sessions), 1)
        session = created_sessions[0]
        self.assertEqual(session.enter_count, 1)
        self.assertEqual(
            session.fetch_calls,
            ["https://xslist.org/search?query=test", "https://xslist.org/person/1"],
        )
        self.assertEqual(first_url, "https://xslist.org/search")
        self.assertEqual(first_body, "<html>search</html>")
        self.assertEqual(second_url, "https://xslist.org/person/1")
        self.assertEqual(second_body, "<html>detail</html>")
        self.assertTrue(session.kwargs["solve_cloudflare"])
        self.assertTrue(session.kwargs["humanize"])
        self.assertTrue(session.kwargs["headless"])
        self.assertTrue(session.kwargs["geoip"])
        self.assertEqual(session.kwargs["proxy"], "http://127.0.0.1:7890")

        xslist.close()
        self.assertEqual(session.exit_count, 1)

    def test_close_before_first_fetch_is_safe(self):
        xslist = XslistSession(session_factory=lambda **kwargs: None)

        xslist.close()

        self.assertIsNone(xslist.session)


if __name__ == "__main__":
    unittest.main()
