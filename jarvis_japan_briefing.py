"""Briefing de notícias úteis para estrangeiros residentes no Japão.

Combina fontes oficiais com um feed jornalístico amplo. O módulo é deliberadamente
provider-light: usa HTTP + XML/HTML da stdlib, sem criar um segundo cliente de IA.
"""
from __future__ import annotations

import html as html_lib
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from typing import Callable
from urllib.parse import quote_plus

import requests

MHLW_NEWS_RSS = "https://www.mhlw.go.jp/stf/news.rdf"
ISA_PORTAL = "https://www.moj.go.jp/isa/support/portal/"
GOOGLE_NEWS_QUERY = (
    "Japan foreign residents OR immigration OR visa OR foreign workers OR foreigners Japan"
)
GOOGLE_NEWS_RSS = (
    "https://news.google.com/rss/search?q=" + quote_plus(GOOGLE_NEWS_QUERY)
    + "&hl=en&gl=JP&ceid=JP:en"
)

FOREIGNER_HINTS = (
    "foreign", "foreigner", "immigration", "visa", "resident", "residence",
    "worker", "employment", "labor", "labour", "my number", "pension",
    "health insurance", "tax", "外国", "在留", "入管", "ビザ", "雇用", "労働",
    "年金", "保険", "マイナンバー", "生活支援", "災害", "地震", "台風",
)


@dataclass(frozen=True)
class NewsItem:
    title: str
    url: str
    source: str
    published: str = ""
    official: bool = False


class JarvisJapanNewsError(RuntimeError):
    pass


def is_japan_news_request(text: str) -> bool:
    value = (text or "").casefold()
    news = any(x in value for x in ("notícia", "noticia", "notícias", "noticias", "news", "briefing"))
    japan = any(x in value for x in ("japão", "japao", "japan", "estrangeir", "imigra", "visto", "residente"))
    return news and japan


def is_daily_briefing_request(text: str) -> bool:
    value = (text or "").casefold()
    return any(x in value for x in (
        "briefing diário", "briefing diario", "resumo do dia", "resumo diário", "resumo diario",
        "me atualize hoje", "atualização do dia", "atualizacao do dia",
    ))


def _get_text(url: str, *, getter: Callable = requests.get, timeout: int = 12) -> str:
    try:
        resp = getter(url, timeout=timeout, headers={"User-Agent": "FaithBloom-Jarvis/1.0"})
        resp.raise_for_status()
        return resp.text
    except requests.RequestException as exc:
        raise JarvisJapanNewsError("Não consegui consultar as notícias do Japão agora.") from exc


def _clean(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value or "")
    return re.sub(r"\s+", " ", html_lib.unescape(value)).strip()


def _parse_google_news(xml_text: str, limit: int = 8) -> list[NewsItem]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    out: list[NewsItem] = []
    for node in root.findall(".//item"):
        title = _clean(node.findtext("title") or "")
        link = (node.findtext("link") or "").strip()
        pub = (node.findtext("pubDate") or "").strip()
        source_node = node.find("source")
        source = _clean(source_node.text if source_node is not None and source_node.text else "Google News")
        if title and link:
            try:
                pub = parsedate_to_datetime(pub).strftime("%Y-%m-%d") if pub else ""
            except (TypeError, ValueError, OverflowError):
                pub = ""
            out.append(NewsItem(title=title, url=link, source=source, published=pub, official=False))
        if len(out) >= limit:
            break
    return out


def _parse_mhlw_rdf(xml_text: str, limit: int = 12) -> list[NewsItem]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    out: list[NewsItem] = []
    for item in root.iter():
        if not item.tag.endswith("item"):
            continue
        title = url = date = ""
        for child in list(item):
            tag = child.tag.rsplit("}", 1)[-1].casefold()
            if tag == "title": title = _clean(child.text or "")
            elif tag in {"link", "about"}: url = (child.text or "").strip()
            elif tag in {"date", "pubdate"}: date = _clean(child.text or "")[:10]
        if title and url and any(h in title.casefold() for h in FOREIGNER_HINTS):
            out.append(NewsItem(title=title, url=url, source="MHLW", published=date, official=True))
        if len(out) >= limit:
            break
    return out


def _parse_isa_updates(page_html: str, limit: int = 6) -> list[NewsItem]:
    text = re.sub(r"\s+", " ", page_html or "")
    # O portal publica atualizações no formato AAAA/MM/DD + texto + link.
    pattern = re.compile(
        r"(?P<date>20\d{2}/\d{1,2}/\d{1,2}).{0,500}?<a[^>]+href=[\"'](?P<href>[^\"']+)[\"'][^>]*>(?P<title>.*?)</a>",
        re.I,
    )
    out: list[NewsItem] = []
    for match in pattern.finditer(text):
        title = _clean(match.group("title"))
        href = match.group("href").strip()
        if not title:
            continue
        if href.startswith("/"):
            href = "https://www.moj.go.jp" + href
        elif not href.startswith("http"):
            href = "https://www.moj.go.jp/isa/support/portal/" + href.lstrip("./")
        out.append(NewsItem(title=title, url=href, source="Immigration Services Agency", published=match.group("date").replace("/", "-"), official=True))
        if len(out) >= limit:
            break
    return out


def fetch_japan_foreigner_news(*, getter: Callable = requests.get, limit: int = 5) -> list[NewsItem]:
    items: list[NewsItem] = []
    failures = 0
    for url, parser in (
        (ISA_PORTAL, _parse_isa_updates),
        (MHLW_NEWS_RSS, _parse_mhlw_rdf),
        (GOOGLE_NEWS_RSS, _parse_google_news),
    ):
        try:
            items.extend(parser(_get_text(url, getter=getter)))
        except JarvisJapanNewsError:
            failures += 1

    dedup: list[NewsItem] = []
    seen: set[str] = set()
    for item in items:
        key = re.sub(r"\W+", " ", item.title.casefold()).strip()
        if not key or key in seen:
            continue
        seen.add(key)
        dedup.append(item)

    dedup.sort(key=lambda x: (not x.official, x.published or "9999-99-99"))
    if not dedup and failures:
        raise JarvisJapanNewsError("As fontes de notícias estão temporariamente indisponíveis.")
    return dedup[: max(1, int(limit))]


def build_japan_news_reply(*, getter: Callable = requests.get, limit: int = 5) -> tuple[str, list[NewsItem]]:
    items = fetch_japan_foreigner_news(getter=getter, limit=limit)
    if not items:
        return "Não encontrei atualizações relevantes para estrangeiros no Japão nas fontes consultadas agora.", []
    spoken = ["Estas são as principais atualizações que encontrei para estrangeiros no Japão."]
    for i, item in enumerate(items[:3], 1):
        tag = "fonte oficial" if item.official else item.source
        spoken.append(f"{i}. {item.title}. {tag}.")
    return " ".join(spoken), items
