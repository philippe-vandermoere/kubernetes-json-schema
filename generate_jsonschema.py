#!/usr/bin/env python3

from datetime import datetime
import logging
import os
from requests import request, models
import time
from typing import Optional

from openapi2jsonschema import cli as openapi2jsonschema

logger = logging.getLogger(__name__)

COMPONENTS: list[dict[str, str]] = [
    {
        "name": "prometheus-operator",
        "github_repository": "prometheus-operator/prometheus-operator",
        "url": "https://github.com/{github_repository}/releases/download/{version}/stripped-down-crds.yaml",
    },
    {
        "name": "cert-manager",
        "github_repository": "cert-manager/cert-manager",
        "url": "https://github.com/{github_repository}/releases/download/{version}/cert-manager.crds.yaml",
    },
    {
        "name": "eck-operator",
        "github_repository": "elastic/cloud-on-k8s",
        "url": "https://download.elastic.co/downloads/eck/{version}/crds.yaml",
    },
    {
        "name": "fluxcd",
        "github_repository": "fluxcd/flux2",
        "url": "https://github.com/{github_repository}/releases/download/{version}/install.yaml",
    },
]


class GithubApi:
    def __init__(self, token: Optional[str] = None):
        self.token = token
        self.api_url: str = "https://api.github.com"

    def _request(
        self,
        route: str,
        method: str = "GET",
        params: Optional[dict[str, list[str]]] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> models.Response:
        if params is None:
            params = {}

        if headers is None:
            headers = {}

        headers["Accept"] = "application/vnd.github+json"
        if self.token is not None:
            headers["Authorization"] = "Bearer " + self.token

        return request(
            method=method,
            url=self.api_url + route,
            headers=headers,
            params=params,
            timeout=10,
        )

    def request(
            self,
            route: str,
            method: str = "GET",
            params: Optional[dict[str, list[str]]] = None,
            headers: Optional[dict[str, str]] = None,
    ) -> models.Response:
        response = self._request(route, method, params, headers)

        if response.status_code == 403 and int(response.headers["X-RateLimit-Remaining"]) == 0:
            reset_date = datetime.fromtimestamp(int(response.headers["X-RateLimit-Reset"]))
            while datetime.now() < reset_date:
                delta = reset_date - datetime.now()
                logger.info(
                    "waiting from github rate limit reset in %ds",
                    delta.seconds
                )
                time.sleep(30)

            response = self._request(route, method, params, headers)

        if response.status_code >= 400:
            raise Exception(response.json())

        return response

    def latest_release(self, repository: str) -> str:
        return self.request(route=f"/repos/{repository}/releases/latest").json()["tag_name"]


def get_github_api() -> GithubApi:
    return GithubApi(os.environ.get("GITHUB_TOKEN"))


def generate_jsonschema_from_url(github_repository: str, url: str):
    openapi2jsonschema([
        url.format(
            version=get_github_api().latest_release(github_repository),
            github_repository=github_repository,
        ),
    ])


if __name__ == '__main__':
    for component in COMPONENTS:
        logger.info("generate json schema for %s", component["name"])
        generate_jsonschema_from_url(
            component["github_repository"],
            component["url"],
        )
