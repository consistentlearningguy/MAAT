"""Reverse image search — pluggable interface for external face search APIs.

This module provides a unified interface for reverse image search services.
Each provider is implemented as a separate class. Currently supported:

- PimEyes (requires API key — paid)
- TinEye (requires API key — paid)
- Google Vision (requires API key — paid)
- Yandex Images (no official API — placeholder for future scraping)

All providers are optional. If no API keys are configured, the module
gracefully returns empty results. The face engine handles local comparison;
this module extends reach to the open web.

Usage:
    from backend.analysis.reverse_image_search import search_all_providers
    results = await search_all_providers(image_path)
"""

import asyncio
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

import httpx
from loguru import logger

from backend.core.config import settings


# ---------------------------------------------------------------------------
# Base class for all reverse image search providers
# ---------------------------------------------------------------------------


class ReverseImageSearchProvider(ABC):
    """Abstract base for reverse image search providers."""

    name: str = "unknown"
    requires_api_key: bool = True

    @abstractmethod
    def is_configured(self) -> bool:
        """Return True if this provider has valid credentials."""
        ...

    @abstractmethod
    async def search(
        self,
        image_path: str | Path,
        limit: int = 10,
    ) -> list[dict]:
        """Search for matching faces/images on the web.

        Args:
            image_path: Path to the face crop image to search
            limit: Max results to return

        Returns:
            List of dicts with:
            - source_url: URL where the matching image was found
            - page_url: URL of the page containing the image
            - thumbnail_url: Thumbnail of the match (if available)
            - similarity: Float 0-1 indicating match confidence
            - title: Page title or description
            - source_name: Name of where the match was found
        """
        ...


# ---------------------------------------------------------------------------
# PimEyes provider
# ---------------------------------------------------------------------------


class PimEyesProvider(ReverseImageSearchProvider):
    """PimEyes face search API.

    PimEyes is a paid facial recognition search engine that searches
    the open web for matching faces. API requires a subscription.

    API docs: https://pimeyes.com/en/api
    """

    name = "pimeyes"
    requires_api_key = True
    _base_url = "https://pimeyes.com/api/search"

    def is_configured(self) -> bool:
        return bool(settings.PIMEYES_API_KEY)

    async def search(
        self,
        image_path: str | Path,
        limit: int = 10,
    ) -> list[dict]:
        if not self.is_configured():
            return []

        image_path = Path(image_path)
        if not image_path.exists():
            logger.warning(f"PimEyes: Image not found: {image_path}")
            return []

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                with open(image_path, "rb") as f:
                    files = {"image": (image_path.name, f, "image/jpeg")}
                    headers = {"Authorization": f"Bearer {settings.PIMEYES_API_KEY}"}

                    response = await client.post(
                        self._base_url,
                        files=files,
                        headers=headers,
                        params={"limit": limit},
                    )
                    response.raise_for_status()

                data = response.json()
                results = []
                for match in data.get("results", [])[:limit]:
                    results.append({
                        "source_url": match.get("imageUrl", ""),
                        "page_url": match.get("pageUrl", ""),
                        "thumbnail_url": match.get("thumbnailUrl", ""),
                        "similarity": match.get("score", 0.0),
                        "title": match.get("title", ""),
                        "source_name": "PimEyes",
                    })

                logger.info(f"PimEyes: Found {len(results)} match(es)")
                return results

        except httpx.HTTPStatusError as e:
            logger.error(f"PimEyes API error: {e.response.status_code} {e.response.text[:200]}")
            return []
        except Exception as e:
            logger.error(f"PimEyes search failed: {e}")
            return []


# ---------------------------------------------------------------------------
# TinEye provider
# ---------------------------------------------------------------------------


class TinEyeProvider(ReverseImageSearchProvider):
    """TinEye reverse image search API.

    TinEye searches for exact and modified copies of images across the web.
    Less useful for face matching but good for finding where a specific
    photo has been reposted.

    API docs: https://services.tineye.com/developers/tineyeapi
    """

    name = "tineye"
    requires_api_key = True
    _base_url = "https://api.tineye.com/rest/search/"

    def is_configured(self) -> bool:
        return bool(settings.TINEYE_API_KEY)

    async def search(
        self,
        image_path: str | Path,
        limit: int = 10,
    ) -> list[dict]:
        if not self.is_configured():
            return []

        image_path = Path(image_path)
        if not image_path.exists():
            logger.warning(f"TinEye: Image not found: {image_path}")
            return []

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                with open(image_path, "rb") as f:
                    files = {"image": (image_path.name, f, "image/jpeg")}
                    params = {
                        "api_key": settings.TINEYE_API_KEY,
                        "limit": limit,
                        "sort": "score",
                        "order": "desc",
                    }

                    response = await client.post(
                        self._base_url,
                        files=files,
                        params=params,
                    )
                    response.raise_for_status()

                data = response.json()
                results = []
                for match in data.get("results", {}).get("matches", [])[:limit]:
                    for backlink in match.get("backlinks", []):
                        results.append({
                            "source_url": match.get("image_url", ""),
                            "page_url": backlink.get("url", ""),
                            "thumbnail_url": "",
                            "similarity": match.get("score", 0.0) / 100.0,  # TinEye uses 0-100
                            "title": backlink.get("url", ""),
                            "source_name": "TinEye",
                        })

                logger.info(f"TinEye: Found {len(results)} match(es)")
                return results[:limit]

        except httpx.HTTPStatusError as e:
            logger.error(f"TinEye API error: {e.response.status_code} {e.response.text[:200]}")
            return []
        except Exception as e:
            logger.error(f"TinEye search failed: {e}")
            return []


# ---------------------------------------------------------------------------
# Google Cloud Vision provider
# ---------------------------------------------------------------------------


class GoogleVisionProvider(ReverseImageSearchProvider):
    """Google Cloud Vision API — web entity detection + reverse image search.

    Uses the Vision API's web detection to find matching and similar images.
    Requires a Google Cloud project with Vision API enabled and an API key.

    API docs: https://cloud.google.com/vision/docs/detecting-web
    """

    name = "google_vision"
    requires_api_key = True
    _base_url = "https://vision.googleapis.com/v1/images:annotate"

    def is_configured(self) -> bool:
        return bool(settings.GOOGLE_VISION_API_KEY)

    async def search(
        self,
        image_path: str | Path,
        limit: int = 10,
    ) -> list[dict]:
        if not self.is_configured():
            return []

        image_path = Path(image_path)
        if not image_path.exists():
            logger.warning(f"Google Vision: Image not found: {image_path}")
            return []

        try:
            import base64

            with open(image_path, "rb") as f:
                image_content = base64.b64encode(f.read()).decode("utf-8")

            body = {
                "requests": [{
                    "image": {"content": image_content},
                    "features": [{"type": "WEB_DETECTION", "maxResults": limit}],
                }]
            }

            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    self._base_url,
                    json=body,
                    params={"key": settings.GOOGLE_VISION_API_KEY},
                )
                response.raise_for_status()

            data = response.json()
            web_detection = (
                data.get("responses", [{}])[0]
                .get("webDetection", {})
            )

            results = []

            # Pages with matching images
            for page in web_detection.get("pagesWithMatchingImages", [])[:limit]:
                results.append({
                    "source_url": page.get("url", ""),
                    "page_url": page.get("url", ""),
                    "thumbnail_url": "",
                    "similarity": page.get("score", 0.5),
                    "title": page.get("pageTitle", ""),
                    "source_name": "Google Vision",
                })

            logger.info(f"Google Vision: Found {len(results)} match(es)")
            return results[:limit]

        except httpx.HTTPStatusError as e:
            logger.error(f"Google Vision API error: {e.response.status_code}")
            return []
        except Exception as e:
            logger.error(f"Google Vision search failed: {e}")
            return []


# ---------------------------------------------------------------------------
# Registry of all providers
# ---------------------------------------------------------------------------

ALL_PROVIDERS: list[ReverseImageSearchProvider] = [
    PimEyesProvider(),
    TinEyeProvider(),
    GoogleVisionProvider(),
]


def get_configured_providers() -> list[ReverseImageSearchProvider]:
    """Return only providers that have valid API keys configured."""
    configured = [p for p in ALL_PROVIDERS if p.is_configured()]
    logger.debug(
        f"Reverse image search: {len(configured)}/{len(ALL_PROVIDERS)} "
        f"providers configured: {[p.name for p in configured]}"
    )
    return configured


async def search_all_providers(
    image_path: str | Path,
    limit_per_provider: int = 10,
) -> list[dict]:
    """Run reverse image search across all configured providers.

    Args:
        image_path: Path to the face crop image
        limit_per_provider: Max results per provider

    Returns:
        Combined list of results from all providers
    """
    providers = get_configured_providers()
    if not providers:
        logger.info("No reverse image search providers configured — skipping")
        return []

    tasks = [
        provider.search(image_path, limit=limit_per_provider)
        for provider in providers
    ]

    results_list = await asyncio.gather(*tasks, return_exceptions=True)

    all_results = []
    for i, result in enumerate(results_list):
        if isinstance(result, Exception):
            logger.error(f"Provider {providers[i].name} failed: {result}")
        else:
            all_results.extend(result)

    logger.info(f"Reverse image search total: {len(all_results)} result(s)")
    return all_results
