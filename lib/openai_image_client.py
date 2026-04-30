"""
OpenAI gpt-image-2.0 を使った画像生成クライアント。

⚠️ モデル名は固定 (gpt-image-2.0)。変更禁止。
   ユーザー側で誤って別モデル（gpt-image-1 等）が使われないようハードコードしている。

GeminiClient.generate_image / generate_image_bytes と同じシグネチャで動く。
"""

from __future__ import annotations

import base64
import io

from openai import OpenAI
from PIL import Image


# ⚠️ 固定。変更禁止。 (.env で上書きも不可)
OPENAI_IMAGE_MODEL = "gpt-image-2.0"


# Gemini のアスペクト比 → OpenAI の size パラメータへのマッピング。
# OpenAI Image API は離散的な size しか受け付けないので、近いものに丸める。
_ASPECT_RATIO_TO_SIZE: dict[str, str] = {
    # 横長
    "16:9": "1536x1024",
    "3:2": "1536x1024",
    "4:3": "1536x1024",
    "5:4": "1536x1024",
    "21:9": "1536x1024",
    # 正方形
    "1:1": "1024x1024",
    # 縦長
    "9:16": "1024x1536",
    "2:3": "1024x1536",
    "3:4": "1024x1536",
    "4:5": "1024x1536",
}


def _to_openai_size(aspect_ratio: str) -> str:
    return _ASPECT_RATIO_TO_SIZE.get(aspect_ratio, "1024x1024")


def _to_openai_quality(image_size: str) -> str:
    # Gemini の "1K" / "2K" / "4K" を OpenAI の quality にマップ
    if image_size == "4K":
        return "high"
    if image_size == "1K":
        return "low"
    return "medium"


# OpenAI images.edit は many-image request で 1枚あたり長辺2000px超を拒否する。
# 余裕を見て1800pxで縮小（縮小後のフォーマット変換等で誤差が出ても安全圏）。
_OPENAI_MAX_REF_DIMENSION = 1800


def _shrink_for_openai(img: Image.Image, max_dim: int = _OPENAI_MAX_REF_DIMENSION) -> Image.Image:
    """参照画像が長辺max_dimを超える場合のみアスペクト比維持で縮小して返す。"""
    w, h = img.size
    longest = max(w, h)
    if longest <= max_dim:
        return img
    scale = max_dim / float(longest)
    new_size = (max(1, int(w * scale)), max(1, int(h * scale)))
    resample = getattr(Image, "Resampling", Image).LANCZOS
    return img.resize(new_size, resample)


class OpenAIImageClient:
    """OpenAI gpt-image-2.0 クライアント。GeminiClient と同じインターフェースを提供。"""

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("OPENAI_API_KEY が設定されていません")
        self.client = OpenAI(api_key=api_key)

    def generate_image(
        self,
        prompt: str,
        reference_images: list[Image.Image] | None = None,
        aspect_ratio: str = "16:9",
        image_size: str = "2K",
        model: str | None = None,  # 互換性のために受け取るが無視する（gpt-image-2.0固定）
    ) -> tuple[Image.Image | None, str | None]:
        """
        OpenAI gpt-image-2.0 で画像を生成。

        Returns:
            (生成画像, レスポンステキスト) のタプル。
            OpenAI は revised_prompt 以外のテキストを返さないので、第2要素は revised_prompt または None。
        """
        size = _to_openai_size(aspect_ratio)
        quality = _to_openai_quality(image_size)

        if reference_images:
            # 参照画像あり → images.edit でスタイルトランスファー
            image_files = []
            for i, ref_img in enumerate(reference_images):
                shrunk = _shrink_for_openai(ref_img)
                buf = io.BytesIO()
                shrunk.save(buf, format="PNG")
                buf.seek(0)
                # OpenAI SDK はファイル名を要求する
                buf.name = f"ref_{i}.png"
                image_files.append(buf)

            response = self.client.images.edit(
                model=OPENAI_IMAGE_MODEL,
                image=image_files if len(image_files) > 1 else image_files[0],
                prompt=prompt,
                size=size,
                quality=quality,
                n=1,
            )
        else:
            response = self.client.images.generate(
                model=OPENAI_IMAGE_MODEL,
                prompt=prompt,
                size=size,
                quality=quality,
                n=1,
            )

        if not response.data:
            return None, None

        item = response.data[0]
        # gpt-image系は b64_json で返ってくる
        b64 = getattr(item, "b64_json", None)
        if not b64:
            return None, getattr(item, "revised_prompt", None)

        image_bytes = base64.b64decode(b64)
        generated_image = Image.open(io.BytesIO(image_bytes))
        revised_prompt = getattr(item, "revised_prompt", None)

        return generated_image, revised_prompt

    def generate_image_bytes(
        self,
        prompt: str,
        reference_images: list[Image.Image] | None = None,
        aspect_ratio: str = "16:9",
        image_size: str = "2K",
        model: str | None = None,
        format: str = "PNG",
    ) -> tuple[bytes | None, str | None]:
        """画像を bytes 形式で返す（Streamlit 表示・DL 用）"""
        image, text = self.generate_image(
            prompt=prompt,
            reference_images=reference_images,
            aspect_ratio=aspect_ratio,
            image_size=image_size,
        )
        if image is None:
            return None, text

        buf = io.BytesIO()
        image.save(buf, format=format)
        return buf.getvalue(), text

    def refine_image(
        self,
        current_image: Image.Image,
        instruction: str,
        reference_images: list[Image.Image] | None = None,
        model: str | None = None,
    ) -> tuple[Image.Image | None, str | None]:
        """既存の画像に対して微修正を加えて再生成する（OpenAI images.edit を使用）。
        instruction は呼び出し側で完成させた指示文（boilerplate含む）を渡すこと。
        """
        # 元画像のアスペクト比に近い size を選ぶ
        w, h = current_image.size
        ratio = w / h if h > 0 else 1.0
        if ratio > 1.2:
            size = "1536x1024"
        elif ratio < 0.83:
            size = "1024x1536"
        else:
            size = "1024x1024"

        # 参照画像 + 現在の画像 をまとめて渡す（OpenAIの2000px制約に合わせて縮小）
        image_files = []
        all_images = (reference_images or []) + [current_image]
        for i, img in enumerate(all_images):
            shrunk = _shrink_for_openai(img)
            buf = io.BytesIO()
            shrunk.save(buf, format="PNG")
            buf.seek(0)
            buf.name = f"refine_{i}.png"
            image_files.append(buf)

        response = self.client.images.edit(
            model=OPENAI_IMAGE_MODEL,
            image=image_files if len(image_files) > 1 else image_files[0],
            prompt=instruction,
            size=size,
            quality="medium",
            n=1,
        )

        if not response.data:
            return None, None
        item = response.data[0]
        b64 = getattr(item, "b64_json", None)
        if not b64:
            return None, getattr(item, "revised_prompt", None)
        gen_image = Image.open(io.BytesIO(base64.b64decode(b64)))
        return gen_image, getattr(item, "revised_prompt", None)
