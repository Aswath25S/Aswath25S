#!/usr/bin/env python3
"""Refresh the public GitHub statistics embedded in the profile SVGs."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
USERNAME = os.environ.get("USER_NAME", "Aswath25S")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
GRAPHQL_URL = "https://api.github.com/graphql"


def graphql(query: str, variables: dict[str, object]) -> dict:
    if not TOKEN:
        raise RuntimeError("GITHUB_TOKEN is required to query GitHub statistics")

    request = urllib.request.Request(
        GRAPHQL_URL,
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": f"{USERNAME}-profile-readme",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise RuntimeError(f"GitHub API returned {exc.code}: {detail}") from exc

    if payload.get("errors"):
        raise RuntimeError(f"GitHub GraphQL error: {payload['errors']}")
    return payload["data"]


def fetch_stats() -> dict[str, int]:
    query = """
    query ProfileStats($login: String!, $cursor: String) {
      user(login: $login) {
        followers { totalCount }
        contributionsCollection {
          contributionCalendar { totalContributions }
        }
        repositories(
          first: 100
          after: $cursor
          ownerAffiliations: OWNER
          privacy: PUBLIC
          isFork: false
        ) {
          totalCount
          nodes { stargazerCount }
          pageInfo { hasNextPage endCursor }
        }
      }
    }
    """

    cursor: str | None = None
    stars = 0
    repo_count = followers = contributions = 0

    while True:
        user = graphql(query, {"login": USERNAME, "cursor": cursor})["user"]
        repos = user["repositories"]
        repo_count = repos["totalCount"]
        followers = user["followers"]["totalCount"]
        contributions = user["contributionsCollection"]["contributionCalendar"][
            "totalContributions"
        ]
        stars += sum(repo["stargazerCount"] for repo in repos["nodes"])
        if not repos["pageInfo"]["hasNextPage"]:
            break
        cursor = repos["pageInfo"]["endCursor"]

    return {
        "repo_data": repo_count,
        "star_data": stars,
        "follower_data": followers,
        "contribution_data": contributions,
    }


def update_svg(path: Path, stats: dict[str, int]) -> None:
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    tree = ET.parse(path)
    root = tree.getroot()
    by_id = {element.get("id"): element for element in root.iter() if element.get("id")}
    for element_id, value in stats.items():
        if element_id not in by_id:
            raise RuntimeError(f"Missing SVG element #{element_id} in {path.name}")
        by_id[element_id].text = f"{value:,}"
    tree.write(path, encoding="utf-8", xml_declaration=True)


def main() -> None:
    stats = fetch_stats()
    for filename in ("dark_mode.svg", "light_mode.svg"):
        update_svg(ROOT / filename, stats)
    print("Updated profile stats:", ", ".join(f"{key}={value:,}" for key, value in stats.items()))


if __name__ == "__main__":
    main()

