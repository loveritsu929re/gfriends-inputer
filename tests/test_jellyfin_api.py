import unittest

from jellyfin_api import JellyfinApi


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise AssertionError("unexpected HTTP error")


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.responses.pop(0)


class JellyfinApiTests(unittest.TestCase):
    def test_authentication_uses_current_authorization_header(self):
        session = FakeSession([FakeResponse(payload={"Items": [], "TotalRecordCount": 0})])
        api = JellyfinApi("http://server/jellyfin", "secret", session=session, version="3.04")

        api.get_persons()

        method, url, kwargs = session.calls[0]
        self.assertEqual(method, "GET")
        self.assertEqual(url, "http://server/jellyfin/Persons")
        self.assertNotIn("api_key", url)
        self.assertIn('Token="secret"', kwargs["headers"]["Authorization"])
        self.assertEqual(kwargs["params"]["personTypes"], "Actor")

    def test_get_persons_follows_pagination(self):
        session = FakeSession([
            FakeResponse(payload={"Items": [{"Id": "1"}], "TotalRecordCount": 2}),
            FakeResponse(payload={"Items": [{"Id": "2"}], "TotalRecordCount": 2}),
        ])
        api = JellyfinApi("http://server", "secret", session=session)

        persons = api.get_persons(page_size=1)

        self.assertEqual([person["Id"] for person in persons], ["1", "2"])
        self.assertEqual(session.calls[1][2]["params"]["startIndex"], 1)

    def test_update_item_merges_with_complete_dto(self):
        session = FakeSession([
            FakeResponse(payload={"Id": "abc", "Name": "Old", "SortName": "Keep"}),
            FakeResponse(status_code=204),
        ])
        api = JellyfinApi("http://server", "secret", session=session)

        api.update_item("abc", {"Name": "New", "Overview": "Bio"})

        request = session.calls[1]
        self.assertEqual(request[0], "POST")
        self.assertEqual(request[2]["json"], {
            "Id": "abc",
            "Name": "New",
            "SortName": "Keep",
            "Overview": "Bio",
        })

    def test_set_item_image_base64_encodes_image_body(self):
        session = FakeSession([FakeResponse(status_code=204)])
        api = JellyfinApi("http://server", "secret", session=session)

        api.set_item_image("abc", b"jpeg bytes")

        request = session.calls[0]
        self.assertEqual(request[2]["data"], b"anBlZyBieXRlcw==")
        self.assertEqual(request[2]["headers"]["Content-Type"], "image/jpeg")


if __name__ == "__main__":
    unittest.main()
