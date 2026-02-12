"""
画像後処理モジュール（Pillow）
トリミング・タイトルテキスト合成・ロゴ配置を行う。
"""

from __future__ import annotations

import io
from PIL import Image, ImageDraw, ImageFont
import numpy as np


def trim_whitespace(image: Image.Image, threshold: int = 245, padding: int = 10) -> Image.Image:
    """
    画像周囲の白/ほぼ白の余白を自動トリミング。

    Args:
        image: 入力画像
        threshold: この値以上のRGB値を「白」と判定（0-255）
        padding: トリミング後に残すパディング（px）
    """
    img_array = np.array(image.convert("RGB"))
    mask = np.any(img_array < threshold, axis=2)

    rows = np.any(mask, axis=1)
    cols = np.any(mask, axis=0)

    if not rows.any() or not cols.any():
        return image

    rmin, rmax = np.where(rows)[0][[0, -1]]
    cmin, cmax = np.where(cols)[0][[0, -1]]

    # パディング追加
    h, w = img_array.shape[:2]
    rmin = max(0, rmin - padding)
    rmax = min(h - 1, rmax + padding)
    cmin = max(0, cmin - padding)
    cmax = min(w - 1, cmax + padding)

    return image.crop((cmin, rmin, cmax + 1, rmax + 1))


def resize_to_target(image: Image.Image, width: int, height: int) -> Image.Image:
    """指定サイズにリサイズ（アスペクト比維持、余白は背景色で埋める）"""
    img = image.copy()
    img.thumbnail((width, height), Image.LANCZOS)

    # キャンバス作成（白背景）
    canvas = Image.new("RGB", (width, height), (255, 255, 255))
    x = (width - img.width) // 2
    y = (height - img.height) // 2
    canvas.paste(img, (x, y))
    return canvas


def add_title_overlay(
    image: Image.Image,
    title_text: str,
    position: str = "bottom",
    font_size: int = 36,
    text_color: str = "#FFFFFF",
    bg_color: str = "#000000",
    bg_opacity: float = 0.6,
    padding_y: int = 20,
    padding_x: int = 30,
) -> Image.Image:
    """
    画像にタイトルテキストのオーバーレイバーを追加。

    Args:
        image: 入力画像
        title_text: タイトル文字列
        position: "top" or "bottom"
        font_size: フォントサイズ
        text_color: テキスト色（hex）
        bg_color: 背景バー色（hex）
        bg_opacity: 背景バーの透明度（0.0-1.0）
    """
    base = image.convert("RGBA")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # フォント読み込み
    font = _load_font(font_size)

    # テキストサイズ計算
    bbox = draw.textbbox((0, 0), title_text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    bar_height = text_height + padding_y * 2

    # 背景バーの位置
    if position == "top":
        bar_y = 0
    else:
        bar_y = base.height - bar_height

    # 背景バー描画（半透明）
    bg_r, bg_g, bg_b = _hex_to_rgb(bg_color)
    bg_alpha = int(bg_opacity * 255)
    draw.rectangle(
        [(0, bar_y), (base.width, bar_y + bar_height)],
        fill=(bg_r, bg_g, bg_b, bg_alpha),
    )

    # テキスト描画
    text_x = (base.width - text_width) // 2
    text_y = bar_y + padding_y
    txt_r, txt_g, txt_b = _hex_to_rgb(text_color)
    draw.text((text_x, text_y), title_text, fill=(txt_r, txt_g, txt_b, 255), font=font)

    result = Image.alpha_composite(base, overlay)
    return result.convert("RGB")


def add_logo(
    image: Image.Image,
    logo_bytes: bytes,
    position: str = "bottom-right",
    size_pct: float = 0.08,
    margin: int = 20,
    opacity: int = 200,
) -> Image.Image:
    """
    ロゴ画像を合成する。

    Args:
        image: 入力画像
        logo_bytes: ロゴ画像のバイト列
        position: 配置位置
        size_pct: 画像幅に対するロゴ幅の割合
        margin: 端からのマージン（px）
        opacity: ロゴの透明度（0-255）
    """
    base = image.convert("RGBA")
    logo = Image.open(io.BytesIO(logo_bytes)).convert("RGBA")

    # ロゴリサイズ
    logo_width = int(base.width * size_pct)
    aspect = logo.height / logo.width
    logo_height = int(logo_width * aspect)
    logo = logo.resize((logo_width, logo_height), Image.LANCZOS)

    # 透明度適用
    alpha = logo.split()[3]
    alpha = alpha.point(lambda p: int(p * opacity / 255))
    logo.putalpha(alpha)

    # 位置計算
    positions = {
        "top-left": (margin, margin),
        "top-right": (base.width - logo_width - margin, margin),
        "bottom-left": (margin, base.height - logo_height - margin),
        "bottom-right": (base.width - logo_width - margin, base.height - logo_height - margin),
        "center": ((base.width - logo_width) // 2, (base.height - logo_height) // 2),
    }
    x, y = positions.get(position, positions["bottom-right"])

    base.paste(logo, (x, y), logo)
    return base.convert("RGB")


def image_to_bytes(image: Image.Image, format: str = "PNG") -> bytes:
    """PIL Image → bytes変換"""
    buf = io.BytesIO()
    image.save(buf, format=format)
    return buf.getvalue()


def bytes_to_image(data: bytes) -> Image.Image:
    """bytes → PIL Image変換"""
    return Image.open(io.BytesIO(data))


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """日本語対応フォントを読み込む（フォールバック付き）"""
    font_paths = [
        # macOS
        "/System/Library/Fonts/ヒラギノ角ゴシック W4.ttc",
        "/System/Library/Fonts/HelveticaNeue.ttc",
        "/Library/Fonts/NotoSansJP-Medium.ttf",
        "/Library/Fonts/NotoSansCJKjp-Medium.otf",
        # Linux
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansJP-Medium.ttf",
        # Windows
        "C:/Windows/Fonts/meiryo.ttc",
        "C:/Windows/Fonts/YuGothM.ttc",
    ]

    for path in font_paths:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue

    return ImageFont.load_default()


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """#rrggbb → (r, g, b)"""
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
