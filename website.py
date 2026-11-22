"""Fetch a public homepage and extract short, visible excerpts."""

from html.parser import HTMLParser
from dataclasses import dataclass
import http.client
import ipaddress
import re
import socket
import ssl
import time
from urllib.parse import quote, urljoin, urlsplit, urlunsplit


class WebsiteError(ValueError):
    pass


MAX_BYTES = 1_000_000
MAX_REDIRECTS = 4
REDIRECTS = {301, 302, 303, 307, 308}
TLS_CONTEXT = ssl.create_default_context()


@dataclass(frozen=True)
class Evidence:
    text: str
    metadata_field: str | None = None


def normalize_url(value):
    value = value.strip()
    if not value or len(value) > 2048 or re.search(r"[\s\x00-\x1f\x7f\\]", value):
        raise WebsiteError("Enter a company website address, such as acme.com.")
    url = value if "://" in value else f"https://{value}"
    try:
        parts = urlsplit(url)
        host = (parts.hostname or "").encode("idna").decode("ascii")
        expected_port = 443 if parts.scheme == "https" else 80
        if (
            parts.scheme not in {"http", "https"}
            or not host
            or "%" in host
            or parts.username is not None
            or parts.port not in {None, expected_port}
        ):
            raise ValueError
    except (ValueError, UnicodeError) as error:
        raise WebsiteError("Use a public HTTP or HTTPS website address.") from error
    netloc = f"[{host}]" if ":" in host else host
    return urlunsplit((
        parts.scheme,
        netloc,
        quote(parts.path or "/", safe="/%:@!$&'()*+,;=-._~"),
        quote(parts.query, safe="/%?:@!$&'()*+,;=-._~"),
        "",
    ))


def public_address(host, port):
    addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    for _, _, _, _, address in addresses:
        ip = ipaddress.ip_address(address[0])
        if not ip.is_global or ip.is_multicast or ip.is_reserved:
            raise WebsiteError("That address does not resolve to a public website.")
    if not addresses:
        raise WebsiteError("That website could not be found.")
    ipv4 = next((entry for entry in addresses if entry[0] == socket.AF_INET), addresses[0])
    return ipv4[4][0]


def connect_to_site(url, timeout):
    parts = urlsplit(url)
    port = 443 if parts.scheme == "https" else 80
    address = public_address(parts.hostname, port)
    connection = http.client.HTTPConnection(parts.hostname, port, timeout=timeout)
    # Connect to the checked address while retaining the hostname for HTTPS and Host.
    connection.sock = socket.create_connection((address, port), timeout=timeout)
    if parts.scheme == "https":
        try:
            connection.sock = TLS_CONTEXT.wrap_socket(
                connection.sock, server_hostname=parts.hostname
            )
        except OSError:
            connection.close()
            raise
    return connection


def fetch_homepage(value):
    url = normalize_url(value)
    deadline = time.monotonic() + 12
    try:
        for _ in range(MAX_REDIRECTS + 1):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError
            connection = connect_to_site(url, min(remaining, 4))
            try:
                parts = urlsplit(url)
                path = urlunsplit(("", "", parts.path, parts.query, ""))
                connection.request("GET", path, headers={
                    "User-Agent": "HomepageOpener/1.0",
                    "Accept": "text/html,application/xhtml+xml",
                })
                response = connection.getresponse()
                location = response.getheader("Location")
                if response.status in REDIRECTS and location:
                    url = normalize_url(urljoin(url, location))
                    continue
                if response.status != 200:
                    raise WebsiteError(f"The website returned HTTP {response.status}. Try its main homepage.")
                if response.headers.get_content_type() not in {"text/html", "application/xhtml+xml"}:
                    raise WebsiteError("That address did not return an HTML page.")
                body = bytearray()
                while len(body) <= MAX_BYTES:
                    if time.monotonic() >= deadline:
                        raise TimeoutError
                    chunk = response.read1(min(65_536, MAX_BYTES + 1 - len(body)))
                    if not chunk:
                        break
                    body.extend(chunk)
                encoding = response.headers.get_content_charset() or "utf-8"
                try:
                    return url, body[:MAX_BYTES].decode(encoding, errors="replace")
                except (LookupError, UnicodeError):
                    return url, body[:MAX_BYTES].decode("utf-8", errors="replace")
            finally:
                connection.close()
    except (OSError, http.client.HTTPException) as error:
        raise WebsiteError("Could not read that website. Check the address or try another homepage.") from error
    raise WebsiteError("The website redirected too many times.")


class HomepageText(HTMLParser):
    BLOCKS = {"h1", "h2", "h3", "p", "li"}
    IGNORED = {"head", "script", "style", "template", "noscript", "nav", "footer", "svg"}
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
            "meta", "param", "source", "track", "wbr"}

    def __init__(self):
        super().__init__()
        self.hidden = []
        self.tag = None
        self.parts = []
        self.blocks = []
        self.descriptions = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "meta" and self.hidden == ["head"]:
            for field in ("name", "property"):
                name = (attrs.get(field) or "").lower()
                if name in {"description", "og:description", "twitter:description"}:
                    content = " ".join((attrs.get("content") or "").split())
                    if content:
                        self.descriptions.setdefault(name, content)
        if self.hidden:
            if tag not in self.VOID:
                self.hidden.append(tag)
            return
        style = attrs.get("style") or ""
        invisible = re.search(r"(?:^|;)\s*(?:display\s*:\s*none|visibility\s*:\s*hidden)\b", style, re.I)
        if tag in self.IGNORED or "hidden" in attrs or attrs.get("aria-hidden") == "true" or invisible:
            if tag not in self.VOID:
                self.hidden.append(tag)
            return
        if tag in self.BLOCKS:
            self.finish_block()
            self.tag = tag
        if tag == "br":
            self.parts.append(" ")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if self.hidden:
            for index in range(len(self.hidden) - 1, -1, -1):
                if self.hidden[index] == tag:
                    del self.hidden[index:]
                    break
        elif tag == self.tag:
            self.finish_block()

    def handle_data(self, data):
        if not self.hidden and self.tag:
            self.parts.append(data)

    def finish_block(self):
        if self.tag and len(self.blocks) < 400:
            self.blocks.append((self.tag, " ".join("".join(self.parts).split())))
        self.tag = None
        self.parts.clear()


def usable_excerpts(block):
    for excerpt in re.split(r"(?<=[.!?])\s+", block):
        if not 30 <= len(excerpt) <= 200 or len(excerpt.split()) < 5:
            continue
        if re.search(r"cookies?|privacy policy|all rights reserved|terms of (use|service)|"
                     r"enable javascript|verify (that )?you are human|access denied|"
                     r"page not found|just a moment|checking your browser", excerpt, re.I):
            continue
        yield excerpt


def evidence_from(html):
    parser = HomepageText()
    parser.feed(html)
    parser.close()
    parser.finish_block()
    candidates = {}
    for index, (tag, block) in enumerate(parser.blocks):
        for excerpt in usable_excerpts(block):
            score = {"h1": 10, "h2": 3, "h3": 2, "p": 4, "li": 0}[tag]
            score += 4 if 55 <= len(excerpt) <= 155 else 0
            score -= min(index, 40) / 5
            score -= 4 if re.search(r"\b(?:[a-z]+_[a-z]+|https?://)\b", excerpt) else 0
            candidates[excerpt] = max(score, candidates.get(excerpt, -100))
    if candidates:
        return [Evidence(excerpt) for excerpt in sorted(candidates, key=candidates.get, reverse=True)[:5]]
    for field in ("description", "og:description", "twitter:description"):
        excerpts = list(usable_excerpts(parser.descriptions.get(field, "")))
        if excerpts:
            return [Evidence(excerpt, field) for excerpt in excerpts[:5]]
    raise WebsiteError("I couldn’t find product copy in the homepage or its description. Try another page on the company’s site.")
