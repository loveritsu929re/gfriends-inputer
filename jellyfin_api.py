# -*- coding: utf-8 -*-
"""Small client for the Jellyfin APIs used by Gfriends Inputer."""

from base64 import b64encode
from urllib.parse import quote

import requests


class JellyfinApi:
    """Wrap the current Jellyfin endpoints used by this project.

    Authentication deliberately uses Jellyfin's ``Authorization`` header.
    The old ``api_key`` query parameter is legacy, leaks into logs, and can be
    disabled by the server.
    """

    def __init__(self, base_url, api_key, session=None, proxies=None, version="unknown"):
        self.base_url = base_url.rstrip("/") + "/"
        self.session = session or requests.Session()
        self.proxies = proxies
        self.authorization = self._build_authorization(api_key, version)
        self._item_lookup_supported = None
        self._item_lookup_user_id = None

    @staticmethod
    def _build_authorization(api_key, version):
        values = {
            "Client": "Gfriends_Inputer",
            "Device": "Python",
            "DeviceId": "gfriends-inputer",
            "Version": version,
            "Token": api_key,
        }
        attributes = ", ".join(
            '{}="{}"'.format(key, quote(str(value), safe=""))
            for key, value in values.items()
        )
        return "MediaBrowser " + attributes

    def _request(self, method, path, allowed_statuses=None, **kwargs):
        headers = {
            "Accept": 'application/json; profile="PascalCase"',
            "Authorization": self.authorization,
        }
        headers.update(kwargs.pop("headers", {}))
        if "proxies" not in kwargs:
            kwargs["proxies"] = self.proxies

        response = self.session.request(
            method,
            self.base_url + path.lstrip("/"),
            headers=headers,
            **kwargs
        )
        if allowed_statuses is None or response.status_code not in allowed_statuses:
            response.raise_for_status()
        return response

    def get_persons(self, person_types=("Actor",), page_size=1000, timeout=60):
        """Return all persons, following Jellyfin pagination via /Items.

        Jellyfin 10.11's dedicated /Persons endpoint ignores ``startIndex``,
        reports the page size instead of the real total and caps at ~999 items
        per page, so /Items is used here to enumerate large libraries reliably.
        """
        persons = []
        seen_ids = set()
        start_index = 0

        while True:
            params = {
                "startIndex": start_index,
                "limit": page_size,
                "recursive": "true",
                "includeItemTypes": "Person",
                "enableImages": "true",
            }
            if person_types:
                params["personTypes"] = ",".join(person_types)

            payload = self._request(
                "GET", "Items", params=params, timeout=timeout
            ).json()
            page = payload.get("Items", payload.get("items", []))
            if not page:
                break

            # Guard against servers that ignore startIndex and repeat pages.
            fresh = [person for person in page if person.get("Id") not in seen_ids]
            if not fresh:
                break
            for person in fresh:
                seen_ids.add(person.get("Id"))
            persons.extend(fresh)

            total = payload.get(
                "TotalRecordCount",
                payload.get("totalRecordCount", len(persons) + len(fresh)),
            )
            if len(persons) >= total:
                break
            start_index += len(fresh)

        return persons

    def get_item(self, item_id, timeout=60):
        path = "Items/{}".format(item_id)
        params = None
        if self._item_lookup_user_id is not None:
            params = {"userId": self._item_lookup_user_id}

        try:
            return self._request(
                "GET", path, params=params, timeout=timeout
            ).json()
        except requests.exceptions.HTTPError as error:
            status_code = (
                error.response.status_code
                if error.response is not None
                else None
            )
            if status_code != 400 or self._item_lookup_user_id is not None:
                raise

            # Jellyfin 10.11.6 documents userId as optional, but some server
            # configurations reject this endpoint unless a real user is
            # supplied. Discover one once and reuse it for subsequent items.
            try:
                users = self._request(
                    "GET", "Users", timeout=timeout
                ).json()
            except requests.exceptions.RequestException:
                raise error
            if not users or not users[0].get("Id"):
                raise error

            self._item_lookup_user_id = users[0]["Id"]
            return self._request(
                "GET",
                path,
                params={"userId": self._item_lookup_user_id},
                timeout=timeout,
            ).json()

    def update_item(self, item_id, changes, timeout=60):
        """Update metadata, falling back for servers that reject item lookup.

        Prefer a complete item DTO. If a server rejects both documented item
        lookup forms with HTTP 400, fall back to the partial DTO accepted by
        Jellyfin/Emby's UpdateItem endpoint. Remember that behavior after the
        first successful fallback so bulk imports do not repeat bad requests.
        """
        lookup_failed = False
        if self._item_lookup_supported is False:
            item = dict(changes)
        else:
            try:
                item = self.get_item(item_id, timeout=timeout)
                item.update(changes)
            except requests.exceptions.HTTPError as error:
                status_code = (
                    error.response.status_code
                    if error.response is not None
                    else None
                )
                if status_code != 400:
                    raise
                item = dict(changes)
                lookup_failed = True

        response = self._request(
            "POST",
            "Items/{}".format(item_id),
            json=item,
            timeout=timeout,
            allowed_statuses=(204,),
        )
        if lookup_failed:
            self._item_lookup_supported = False
        elif self._item_lookup_supported is None:
            self._item_lookup_supported = True
        return response

    def set_item_image(self, item_id, image_data, image_type="Primary", content_type="image/jpeg", timeout=60):
        # Jellyfin's image controller consumes a base64 encoded request body.
        return self._request(
            "POST",
            "Items/{}/Images/{}".format(item_id, image_type),
            data=b64encode(image_data),
            headers={"Content-Type": content_type},
            timeout=timeout,
            allowed_statuses=(204,),
        )

    def delete_item_image(self, item_id, image_type="Primary", timeout=60):
        # A missing image is already the desired end state.
        return self._request(
            "DELETE",
            "Items/{}/Images/{}".format(item_id, image_type),
            timeout=timeout,
            allowed_statuses=(204, 404),
        )
