import jarvis_japan_briefing as briefing
import jarvis_voice as voice


class FakeResponse:
    def __init__(self, text):
        self.text = text
    def raise_for_status(self):
        return None


def test_news_intent_detection():
    assert briefing.is_japan_news_request("Jarvis, quais são as notícias para estrangeiros no Japão hoje?")
    assert briefing.is_daily_briefing_request("Jarvis, me dê meu briefing diário")
    assert not briefing.is_japan_news_request("Continue meu livro da Mel")


def test_google_news_parser_preserves_source_and_date():
    xml = """<?xml version='1.0'?><rss><channel><item>
    <title>Japan updates visa process - Example News</title>
    <link>https://example.com/story</link>
    <pubDate>Thu, 10 Sep 2026 02:00:00 GMT</pubDate>
    <source>Example News</source>
    </item></channel></rss>"""
    items = briefing._parse_google_news(xml)
    assert len(items) == 1
    assert items[0].source == "Example News"
    assert items[0].published == "2026-09-10"
    assert items[0].official is False


def test_fetch_news_combines_official_and_journalistic_sources():
    isa_html = """2026/09/10 <a href='/isa/news/example.html'>Atualização para residentes estrangeiros</a>"""
    mhlw_xml = """<?xml version='1.0'?><rdf:RDF xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'>
    <item><title>外国人雇用のお知らせ</title><link>https://www.mhlw.go.jp/example</link></item></rdf:RDF>"""
    google_xml = """<?xml version='1.0'?><rss><channel><item><title>Foreign residents in Japan update</title><link>https://news.example/x</link><source>News Example</source></item></channel></rss>"""

    def getter(url, **kwargs):
        if "moj.go.jp" in url:
            return FakeResponse(isa_html)
        if "mhlw.go.jp" in url:
            return FakeResponse(mhlw_xml)
        return FakeResponse(google_xml)

    items = briefing.fetch_japan_foreigner_news(getter=getter, limit=5)
    assert any(item.official for item in items)
    assert any(not item.official for item in items)


def test_voice_routes_japan_news_before_editorial(monkeypatch):
    monkeypatch.setattr(voice, "build_japan_news_reply", lambda **kwargs: ("Notícias do Japão prontas.", []))
    reply = voice.build_spoken_reply("Quais as principais notícias para estrangeiros no Japão hoje?")
    assert reply == "Notícias do Japão prontas."


def test_daily_briefing_combines_toyohashi_weather_and_news(monkeypatch):
    monkeypatch.setattr(voice, "build_weather_reply", lambda location, **kwargs: f"Clima consultado em {location}.")
    monkeypatch.setattr(voice, "build_japan_news_reply", lambda **kwargs: ("Notícias para estrangeiros.", []))
    reply = voice.build_spoken_reply("Jarvis, me dê meu briefing diário")
    assert "Toyohashi" in reply
    assert "Notícias para estrangeiros" in reply
