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
        """Return all matching persons, following Jellyfin pagination."""
        persons = []
        start_index = 0

        while True:
            params = {
                "startIndex": start_index,
                "limit": page_size,
                "enableImages": "true",
            }
            if person_types:
                params["personTypes"] = ",".join(person_types)

            payload = self._request(
                "GET", "Persons", params=params, timeout=timeout
            ).json()
            page = payload.get("Items", payload.get("items", []))
            total = payload.get(
                "TotalRecordCount",
                payload.get("totalRecordCount", len(persons) + len(page)),
            )
            persons.extend(page)

            if not page or len(persons) >= total:
                break
            start_index += len(page)

        return persons

    def get_item(self, item_id, timeout=60):
        return self._request(
            "GET", "Items/{}".format(item_id), timeout=timeout
        ).json()

    def update_item(self, item_id, changes, timeout=60):
        """Merge changes into the complete DTO required by UpdateItem."""
        item = self.get_item(item_id, timeout=timeout)
        item.update(changes)
        return self._request(
            "POST",
            "Items/{}".format(item_id),
            json=item,
            timeout=timeout,
            allowed_statuses=(204,),
        )

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
