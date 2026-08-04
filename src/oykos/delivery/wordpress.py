"""Publish each issue to WordPress via the REST API.

Uses the core `/wp-json/wp/v2/posts` endpoint with an Application Password
(WordPress 5.6+, Users > Profile > Application Passwords). Nothing needs to be
installed on the site.

The published post becomes the issue's public archive page, which the email
links to as "Leggi online".
"""
from __future__ import annotations

import base64
import logging

import httpx

from oykos.config import Settings
from oykos.models.news_item import Newsletter

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 30.0
CREATED = 201


def _auth_header(settings: Settings) -> str:
    token = f"{settings.wordpress_user}:{settings.wordpress_app_password.get_secret_value()}"
    return "Basic " + base64.b64encode(token.encode("utf-8")).decode("ascii")


def build_post_payload(settings: Settings, newsletter: Newsletter) -> dict[str, object]:
    """Map an issue onto a WordPress post."""
    payload: dict[str, object] = {
        "title": newsletter.subject_line or f"{settings.newsletter_title} - {newsletter.week}",
        "slug": f"briefing-{newsletter.week.lower()}",
        "content": newsletter.html_content,
        "excerpt": newsletter.preheader,
        "status": settings.wordpress_status,
    }
    if settings.wordpress_category_id:
        payload["categories"] = [settings.wordpress_category_id]
    return payload


async def publish_issue(settings: Settings, newsletter: Newsletter) -> str:
    """Publish the issue and return its public URL, or an empty string on failure."""
    if not settings.wordpress_enabled:
        return ""

    url = f"{settings.wordpress_url.rstrip('/')}/wp-json/wp/v2/posts"
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            response = await client.post(
                url,
                json=build_post_payload(settings, newsletter),
                headers={"Authorization": _auth_header(settings)},
            )
    except httpx.HTTPError:
        logger.exception("WordPress publish failed for %s", newsletter.week)
        return ""

    if response.status_code != CREATED:
        logger.error(
            "WordPress rejected the post (%d): %.300s",
            response.status_code,
            response.text,
        )
        return ""

    link = str(response.json().get("link", ""))
    logger.info("Published %s to WordPress: %s", newsletter.week, link)
    return link
