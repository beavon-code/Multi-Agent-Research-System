from langchain.tools import tool
import requests
from dotenv import load_dotenv
import os
from tavily import TavilyClient
from bs4 import BeautifulSoup
from readability import Document
import trafilatura
import re

load_dotenv()

tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

@tool
def web_search(query: str):
    """Search the web for recent and reliable information on a topic. Returns Titles, URL and Content"""
    results = tavily.search(query=query, max_results=5)

    out = []

    for r in results['results']:
        out.append(f"Title: {r['title']}\nURL: {r['url']}\nSnippet: {r['content'][:300]}\n")

    return "\n------\n".join(out)  


@tool
def scrape_url(url: str, timeout: int = 15, min_words: int = 50) -> str:
    """
    Scrape and extract clean readable content from a url.
    Uses multiple extraction strategies for better reliability.
 
    Returns the extracted text, or an empty string if nothing readable was found.
    Requires: requests, beautifulsoup4. Optional (better results): trafilatura, readability-lxml.
    """
    # 1. Fetch the page
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        if not resp.encoding or resp.encoding.lower() == "iso-8859-1":
            resp.encoding = resp.apparent_encoding
        html = resp.text
    except requests.RequestException:
        return ""
 
    noise_tags = ["script", "style", "noscript", "iframe", "svg", "form",
                  "nav", "header", "footer", "aside", "button"]
 
    def clean(text: str) -> str:
        lines, seen = [], set()
        for line in (text or "").replace("\xa0", " ").splitlines():
            line = re.sub(r"\s+", " ", line).strip()
            if line and line.lower() not in seen:
                seen.add(line.lower())
                lines.append(line)
        return "\n".join(lines)
 
    def soup_without_noise():
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(noise_tags):
            tag.decompose()
        return soup
 
    # 2. Extraction strategies, best first
    def with_trafilatura():
        import trafilatura
        return trafilatura.extract(html, url=url, include_comments=False) or ""
 
    def with_readability():
        from readability import Document
        return BeautifulSoup(Document(html).summary(), "html.parser").get_text("\n")
 
    def with_semantic_tags():
        found = soup_without_noise().select(
            "article, main, [role=main], #content, .post-content, .entry-content, .article-body")
        return max(found, key=lambda el: len(el.get_text()), default=None).get_text("\n") if found else ""
 
    def with_paragraphs():
        soup = soup_without_noise()
        return "\n".join(el.get_text(" ", strip=True)
                         for el in soup.find_all(["h1", "h2", "h3", "p", "li", "blockquote"]))
 
    # 3. Return the first result with enough words, otherwise the longest
    best = ""
    for strategy in (with_trafilatura, with_readability, with_semantic_tags, with_paragraphs):
        try:
            text = clean(strategy())
        except Exception:  # missing library or parse error -> try the next one
            continue
        if len(text.split()) >= min_words:
            return text
        if len(text) > len(best):
            best = text
    return best