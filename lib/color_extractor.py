"""
サイトURLからカラーパレットを自動抽出するモジュール
CSS解析（inline style + <style>タグ + 外部CSS）でカラーコードを収集し、
出現頻度と用途で分類する。
"""

from __future__ import annotations

import re
from collections import Counter
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
import tinycss2
from tinycss2 import color3


def extract_colors_from_url(url: str, top_n: int = 20) -> dict:
    """
    サイトURLからカラーパレットを抽出する。

    Returns:
        {
            "suggested": {
                "primary": "#...",
                "secondary": "#...",
                "accent": "#...",
                "background": "#...",
                "text": "#...",
            },
            "all_colors": [{"hex": "#...", "count": N, "properties": [...]}, ...],
        }
    """
    css_texts = _fetch_all_css(url)
    color_data = _parse_colors(css_texts)
    suggested = _categorize_colors(color_data)

    # 上位N色を返す
    top_colors = sorted(
        color_data.items(),
        key=lambda x: -x[1]["count"],
    )[:top_n]

    return {
        "suggested": suggested,
        "all_colors": [
            {
                "hex": hex_color,
                "count": data["count"],
                "properties": list(data["properties"])[:5],
            }
            for hex_color, data in top_colors
        ],
    }


def _fetch_all_css(url: str) -> list[str]:
    """URL先のHTML内の全CSSを収集"""
    headers = {"User-Agent": "Mozilla/5.0 (compatible; SEOImageGen/1.0)"}
    try:
        resp = requests.get(url, timeout=15, headers=headers)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise ConnectionError(f"URLの取得に失敗しました: {e}")

    soup = BeautifulSoup(resp.text, "html.parser")
    css_texts = []

    # <style>タグ
    for style_tag in soup.find_all("style"):
        if style_tag.string:
            css_texts.append(style_tag.string)

    # 外部CSS（<link rel="stylesheet">）
    for link in soup.find_all("link", rel="stylesheet"):
        href = link.get("href")
        if href:
            css_url = urljoin(url, href)
            try:
                css_resp = requests.get(css_url, timeout=10, headers=headers)
                css_resp.raise_for_status()
                css_texts.append(css_resp.text)
            except requests.RequestException:
                continue

    # inline style属性
    for tag in soup.find_all(style=True):
        css_texts.append(f"dummy {{ {tag['style']} }}")

    return css_texts


def _parse_colors(css_texts: list[str]) -> dict:
    """
    CSS文字列群からカラーコードを抽出。
    tinycss2パーサ + regexフォールバックの二重抽出。

    Returns:
        {"#abcdef": {"count": N, "properties": {"color", "background-color", ...}}, ...}
    """
    color_data: dict[str, dict] = {}

    def _add_color(hex_color: str, prop: str = "unknown"):
        hex_color = hex_color.lower()
        if hex_color not in color_data:
            color_data[hex_color] = {"count": 0, "properties": set()}
        color_data[hex_color]["count"] += 1
        color_data[hex_color]["properties"].add(prop)

    # tinycss2 パーサ
    for css_text in css_texts:
        try:
            rules = tinycss2.parse_stylesheet(
                css_text, skip_comments=True, skip_whitespace=True
            )
            for rule in rules:
                if not hasattr(rule, "content") or rule.content is None:
                    continue
                decls = tinycss2.parse_declaration_list(
                    rule.content, skip_comments=True, skip_whitespace=True
                )
                for decl in decls:
                    if not hasattr(decl, "value"):
                        continue
                    prop_name = getattr(decl, "lower_name", "unknown")
                    for token in decl.value:
                        parsed = color3.parse_color(token)
                        if parsed and parsed != "currentColor":
                            r = max(0, min(255, int(parsed.red * 255)))
                            g = max(0, min(255, int(parsed.green * 255)))
                            b = max(0, min(255, int(parsed.blue * 255)))
                            hex_c = f"#{r:02x}{g:02x}{b:02x}"
                            _add_color(hex_c, prop_name)
        except Exception:
            continue

    # Regexフォールバック（tinycss2で拾えない記法対応）
    hex_pattern = re.compile(r"#(?:[0-9a-fA-F]{3}){1,2}\b")
    for css_text in css_texts:
        for match in hex_pattern.findall(css_text):
            normalized = match.lower()
            if len(normalized) == 4:
                normalized = f"#{normalized[1]*2}{normalized[2]*2}{normalized[3]*2}"
            _add_color(normalized, "regex")

    return color_data


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """#rrggbb → (r, g, b)"""
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _brightness(hex_color: str) -> float:
    """0-255の明度を返す（人間の知覚に近いweighted）"""
    r, g, b = _hex_to_rgb(hex_color)
    return 0.299 * r + 0.587 * g + 0.114 * b


def _categorize_colors(color_data: dict) -> dict:
    """
    抽出したカラーデータをprimary/secondary/accent/background/textに分類。
    ヒューリスティック:
    - background-color系で最頻出の明るい色 → background
    - color系で最頻出の暗い色 → text
    - 残りの高頻出色 → primary, secondary, accent
    """
    bg_colors = []
    text_colors = []
    accent_colors = []

    for hex_color, data in color_data.items():
        brightness = _brightness(hex_color)
        props = data["properties"]
        count = data["count"]

        # 白・黒に近すぎる色は除外（背景・テキスト候補のみ）
        if brightness > 240:
            bg_colors.append((hex_color, count))
            continue
        if brightness < 30:
            text_colors.append((hex_color, count))
            continue

        # プロパティで分類
        if any("background" in p for p in props):
            if brightness > 200:
                bg_colors.append((hex_color, count))
            else:
                accent_colors.append((hex_color, count * 2))
        elif any(p == "color" for p in props):
            if brightness < 80:
                text_colors.append((hex_color, count))
            else:
                accent_colors.append((hex_color, count))
        else:
            accent_colors.append((hex_color, count))

    # ソートして最頻出を選択
    bg_colors.sort(key=lambda x: -x[1])
    text_colors.sort(key=lambda x: -x[1])
    accent_colors.sort(key=lambda x: -x[1])

    return {
        "background": bg_colors[0][0] if bg_colors else "#ffffff",
        "text": text_colors[0][0] if text_colors else "#1f2937",
        "primary": accent_colors[0][0] if len(accent_colors) > 0 else "#3b82f6",
        "secondary": accent_colors[1][0] if len(accent_colors) > 1 else "#10b981",
        "accent": accent_colors[2][0] if len(accent_colors) > 2 else "#f59e0b",
    }
