"""Web mention scanner.

Searches for a missing person's name across public web sources to find
mentions, sightings, news articles, and social media posts.

Sources:
1. Google News (via RSS) — news articles about the case
2. Reddit search — public posts mentioning the person
3. Google web search (via scraping) — general web mentions
4. Twitter/X search (public, no API needed for basic search)

The goal: find any public post, article, or mention that contains
location information or recent activity related to the missing person.
"""

import asyncio
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import quote_plus

import httpx
from loguru import logger


USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"


def _clean_html(text: str) -> str:
    """Strip HTML tags from a string."""
    return re.sub(r'<[^>]+>', '', text).strip()


def _extract_snippet(text: str, max_length: int = 500) -> str:
    """Extract a clean snippet from text content."""
    clean = _clean_html(text)
    if len(clean) > max_length:
        return clean[:max_length] + "..."
    return clean


async def search_google_news(
    client: httpx.AsyncClient,
    query: str,
    max_results: int = 20,
) -> list[dict]:
    """Search Google News RSS for articles about a person.
    
    Google News RSS is publicly accessible and doesn't require an API key.
    This is the most reliable source for finding news coverage of a case.
    """
    results = []
    encoded_query = quote_plus(query)
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-CA&gl=CA&ceid=CA:en"

    try:
        resp = await client.get(url, timeout=15.0)
        if resp.status_code != 200:
            logger.warning(f"Google News returned HTTP {resp.status_code} for query '{query}'")
            return results

        # Parse RSS XML
        root = ET.fromstring(resp.text)
        channel = root.find('channel')
        if channel is None:
            logger.warning(f"Google News RSS had no <channel> element for query '{query}'")
            return results

        items = channel.findall('item')[:max_results]

        for item in items:
            title_el = item.find('title')
            link_el = item.find('link')
            pub_date_el = item.find('pubDate')
            desc_el = item.find('description')
            source_el = item.find('source')

            title = title_el.text if title_el is not None else ""
            link = link_el.text if link_el is not None else ""
            pub_date_str = pub_date_el.text if pub_date_el is not None else ""
            description = _clean_html(desc_el.text) if desc_el is not None and desc_el.text else ""
            source_name = source_el.text if source_el is not None else "Google News"

            # Parse pub date
            content_date = None
            if pub_date_str:
                try:
                    # Format: "Sat, 15 Mar 2026 12:00:00 GMT"
                    content_date = datetime.strptime(
                        pub_date_str.strip(), "%a, %d %b %Y %H:%M:%S %Z"
                    ).replace(tzinfo=timezone.utc)
                except ValueError:
                    pass

            results.append({
                "source": "google_news",
                "source_name": source_name,
                "title": title,
                "url": link,
                "content": description,
                "content_date": content_date,
                "query": query,
            })

    except Exception as e:
        logger.error(f"Google News search failed for '{query}': {e}")

    return results


async def search_reddit(
    client: httpx.AsyncClient,
    query: str,
    max_results: int = 25,
) -> list[dict]:
    """Search Reddit's public JSON API for posts mentioning a person.
    
    Reddit's search API is public (no auth needed) and returns JSON.
    Subreddits like r/missingpersons, r/canada, r/rbi are particularly relevant.
    """
    results = []
    encoded_query = quote_plus(query)
    
    # Search across all of reddit, sorted by relevance
    url = f"https://www.reddit.com/search.json?q={encoded_query}&sort=relevance&t=all&limit={max_results}"

    try:
        resp = await client.get(url, timeout=15.0)
        if resp.status_code != 200:
            logger.warning(f"Reddit search returned {resp.status_code} for query '{query}'")
            return results

        data = resp.json()
        posts = data.get("data", {}).get("children", [])

        for post in posts:
            pdata = post.get("data", {})

            title = pdata.get("title", "")
            selftext = pdata.get("selftext", "")
            permalink = pdata.get("permalink", "")
            subreddit = pdata.get("subreddit", "")
            created_utc = pdata.get("created_utc")
            score = pdata.get("score", 0)
            num_comments = pdata.get("num_comments", 0)

            content_date = None
            if created_utc:
                content_date = datetime.fromtimestamp(created_utc, tz=timezone.utc)

            full_url = f"https://www.reddit.com{permalink}" if permalink else ""

            content = _extract_snippet(selftext) if selftext else ""
            if not content:
                content = title

            results.append({
                "source": "reddit",
                "source_name": f"r/{subreddit}",
                "title": title,
                "url": full_url,
                "content": content,
                "content_date": content_date,
                "query": query,
                "extra": {
                    "subreddit": subreddit,
                    "score": score,
                    "num_comments": num_comments,
                },
            })

    except Exception as e:
        logger.error(f"Reddit search failed for '{query}': {e}")

    return results


async def search_duckduckgo_html(
    client: httpx.AsyncClient,
    query: str,
    max_results: int = 20,
) -> list[dict]:
    """Search DuckDuckGo HTML version for general web mentions.
    
    We use the HTML lite version which is more stable for scraping
    and doesn't require JavaScript. This finds blog posts, forums,
    community posts, and other web pages mentioning the person.
    """
    results = []
    encoded_query = quote_plus(query)
    url = f"https://html.duckduckgo.com/html/?q={encoded_query}"

    try:
        resp = await client.get(url, timeout=15.0)
        if resp.status_code != 200:
            logger.warning(f"DuckDuckGo returned {resp.status_code} for query '{query}'")
            return results

        html = resp.text

        # Parse results from DDG HTML
        # Results are in <div class="result"> blocks
        result_blocks = re.findall(
            r'<a[^>]+class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>.*?'
            r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>',
            html,
            re.DOTALL,
        )

        for link, title_html, snippet_html in result_blocks[:max_results]:
            title = _clean_html(title_html)
            content = _clean_html(snippet_html)

            # DDG sometimes wraps URLs in redirect
            if "uddg=" in link:
                match = re.search(r'uddg=([^&]+)', link)
                if match:
                    from urllib.parse import unquote
                    link = unquote(match.group(1))

            if title and link:
                results.append({
                    "source": "duckduckgo",
                    "source_name": "Web Search",
                    "title": title,
                    "url": link,
                    "content": content,
                    "content_date": None,
                    "query": query,
                })

    except Exception as e:
        logger.error(f"DuckDuckGo search failed for '{query}': {e}")

    return results


def build_search_queries(
    name: str,
    city: Optional[str] = None,
    province: Optional[str] = None,
) -> list[str]:
    """Build search queries for a missing person.
    
    Generates multiple query variations to maximize coverage:
    - Exact name + "missing"
    - Name + city
    - Name + province  
    - Name + "found" / "located" / "sighting"
    """
    queries = []
    clean_name = name.strip()

    if not clean_name:
        return queries

    # Province display name mapping
    province_map = {
        "Alberta": "Alberta", "BritishColumbia": "British Columbia",
        "Manitoba": "Manitoba", "NewBrunswick": "New Brunswick",
        "NewfoundlandandLabrador": "Newfoundland", "NT": "Northwest Territories",
        "NovaScotia": "Nova Scotia", "NU": "Nunavut", "Ontario": "Ontario",
        "PrinceEdwardIsland": "PEI", "Quebec": "Quebec",
        "Saskatchewan": "Saskatchewan", "YT": "Yukon",
    }
    prov_display = province_map.get(province, province) if province else None

    # Core queries
    queries.append(f'"{clean_name}" missing')
    queries.append(f'"{clean_name}" missing child Canada')

    if city:
        queries.append(f'"{clean_name}" {city}')
        queries.append(f'"{clean_name}" missing {city}')

    if prov_display:
        queries.append(f'"{clean_name}" missing {prov_display}')

    # Recovery-oriented queries
    queries.append(f'"{clean_name}" found')
    queries.append(f'"{clean_name}" located')
    queries.append(f'"{clean_name}" sighting')

    return queries


async def scan_web_mentions(
    name: str,
    city: Optional[str] = None,
    province: Optional[str] = None,
    max_queries: int = 8,
) -> list[dict]:
    """Run all web mention searches for a missing person.
    
    This is the main entry point. Searches Google News, Reddit, and
    DuckDuckGo for mentions of the person.
    
    Returns a flat list of all mentions found.
    """
    queries = build_search_queries(name, city, province)[:max_queries]
    
    if not queries:
        logger.warning(f"No search queries generated for name='{name}'")
        return []

    logger.info(f"Scanning web mentions for '{name}' with {len(queries)} queries...")

    all_results = []
    seen_urls = set()

    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
    ) as client:
        for i, query in enumerate(queries):
            logger.debug(f"  Query {i+1}/{len(queries)}: {query}")

            # Run all sources in parallel for each query
            news_task = search_google_news(client, query)
            reddit_task = search_reddit(client, query)
            ddg_task = search_duckduckgo_html(client, query)

            results_batch = await asyncio.gather(
                news_task, reddit_task, ddg_task,
                return_exceptions=True,
            )

            # Collect results, deduplicating by URL
            source_names = ["Google News", "Reddit", "DuckDuckGo"]
            for source_name, batch in zip(source_names, results_batch):
                if isinstance(batch, BaseException):
                    logger.error(f"  {source_name} search failed for query '{query}': {batch}")
                    continue
                batch_count = 0
                for result in batch:  # type: ignore[union-attr]
                    url = result.get("url", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        all_results.append(result)
                        batch_count += 1
                if batch_count > 0:
                    logger.debug(f"  {source_name}: {batch_count} new results for query '{query}'")

            # Rate limiting between queries
            if i < len(queries) - 1:
                await asyncio.sleep(1.0)

    logger.info(f"Web scan complete: {len(all_results)} unique mentions for '{name}'")
    return all_results
