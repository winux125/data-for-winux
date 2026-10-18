"""Public-text helpers used only by the explicit corpus collection command.

Inference never calls request(). Kept inside the package so importing the offline
collector's parsers does not require the historical experiment directory.
"""
from html.parser import HTMLParser
import json
import re
from urllib.request import Request, urlopen

BASE = 'https://adilet.zan.kz'


class Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in ('p', 'div', 'br', 'h1', 'h2', 'h3', 'h4', 'tr', 'li'):
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in ('p', 'div', 'h1', 'h2', 'h3', 'h4', 'tr', 'li'):
            self.parts.append('\n')

    def handle_data(self, data):
        self.parts.append(data)

    def text(self):
        lines = [re.sub(r'\s+', ' ', x).strip() for x in ''.join(self.parts).splitlines()]
        return '\n'.join(x for x in lines if x) + '\n'


def request(path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = Request(BASE + path, data=data, headers={
        'Content-Type': 'application/json', 'User-Agent': 'ForteBank-research-source-snapshot/1'})
    with urlopen(req, timeout=30) as response:
        return json.load(response)
