"""
記事分析モジュール
記事本文からH2/H3構造を解析し、Geminiで画像案3-5個を生成する。
"""

from __future__ import annotations

import json
import re
from lib.gemini_client import GeminiClient
from lib.prompt_templates import render_proposal_prompt, render_mv_proposal_prompt


def extract_headings(article_text: str) -> list[dict]:
    """
    記事本文からH2/H3見出しを抽出する。
    Markdown（## / ###）とHTML（<h2>, <h3>）両対応。

    Returns:
        [{"level": 2, "text": "見出しテキスト", "line": 行番号}, ...]
    """
    headings = []
    lines = article_text.split("\n")

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Markdown形式
        if stripped.startswith("### "):
            headings.append({
                "level": 3,
                "text": stripped.lstrip("#").strip(),
                "line": i + 1,
            })
        elif stripped.startswith("## "):
            headings.append({
                "level": 2,
                "text": stripped.lstrip("#").strip(),
                "line": i + 1,
            })

        # HTML形式
        h2_match = re.search(r"<h2[^>]*>(.*?)</h2>", stripped, re.IGNORECASE)
        if h2_match:
            text = re.sub(r"<[^>]+>", "", h2_match.group(1)).strip()
            if text:
                headings.append({"level": 2, "text": text, "line": i + 1})

        h3_match = re.search(r"<h3[^>]*>(.*?)</h3>", stripped, re.IGNORECASE)
        if h3_match:
            text = re.sub(r"<[^>]+>", "", h3_match.group(1)).strip()
            if text:
                headings.append({"level": 3, "text": text, "line": i + 1})

    return headings


def propose_images(
    article_text: str,
    site_config: dict,
    gemini: GeminiClient,
) -> list[dict]:
    """
    記事本文をGeminiで分析し、画像案3-5個をJSON形式で返す。

    Returns:
        [
          {
            "placement": "H2: ...",
            "purpose": "...",
            "conclusion": "...",
            "layout_type": "分類型",
            "layout_reason": "...",
            "blocks": [{"heading": "...", "description": "..."}],
            "composition_description": "..."
          },
          ...
        ]
    """
    prompt = render_proposal_prompt(article_text, site_config)
    response_text = gemini.analyze_text(prompt)

    proposals = _parse_proposals(response_text)
    return proposals


def propose_mv_images(
    article_title: str,
    article_text: str,
    gemini: GeminiClient,
) -> list[dict]:
    """
    記事タイトルと本文からMV画像案を1-3個生成する。

    Returns:
        [
          {
            "concept": "...",
            "scene_description": "...",
            "composition_type": "中央配置型|左右分割型|シーン描写型|アイコン散りばめ型",
            "text_area": "上部|下部|左|右",
            "mood": "...",
            "main_elements": ["...", "..."],
            "background_description": "..."
          },
          ...
        ]
    """
    prompt = render_mv_proposal_prompt(article_title, article_text)
    response_text = gemini.analyze_text(prompt)

    proposals = _parse_proposals(response_text)
    return proposals


def _parse_proposals(response_text: str) -> list[dict]:
    """
    GeminiのレスポンスからJSON配列を抽出してパースする。
    コードブロックで囲まれている場合も対応。
    """
    # ```json ... ``` ブロックを抽出
    code_block_match = re.search(
        r"```(?:json)?\s*\n?(.*?)```",
        response_text,
        re.DOTALL,
    )

    json_text = code_block_match.group(1).strip() if code_block_match else response_text.strip()

    # JSON配列の開始/終了を見つける
    start = json_text.find("[")
    end = json_text.rfind("]")
    if start == -1 or end == -1:
        return []

    json_text = json_text[start : end + 1]

    try:
        proposals = json.loads(json_text)
        if isinstance(proposals, list):
            return proposals
    except json.JSONDecodeError:
        pass

    return []
