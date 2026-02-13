"""
Gemini APIラッパー
テキスト分析（gemini-2.5-flash）と画像生成（gemini-3-pro-image-preview）を統一的に扱う。
"""

from __future__ import annotations

from google import genai
from google.genai import types
from PIL import Image
import io


# サポートされるアスペクト比
SUPPORTED_ASPECT_RATIOS = [
    "1:1", "2:3", "3:2", "3:4", "4:3",
    "4:5", "5:4", "9:16", "16:9", "21:9",
]

# サポートされる画像サイズ
SUPPORTED_IMAGE_SIZES = ["1K", "2K", "4K"]

# モデルID
MODEL_ANALYSIS = "gemini-2.5-flash"
MODEL_IMAGE = "gemini-3-pro-image-preview"


class GeminiClient:
    """Gemini API クライアント"""

    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)

    def analyze_text(
        self,
        prompt: str,
        model: str = MODEL_ANALYSIS,
    ) -> str:
        """テキスト分析（記事構造解析・画像案提案等）"""
        response = self.client.models.generate_content(
            model=model,
            contents=prompt,
        )
        return response.text

    def analyze_with_images(
        self,
        prompt: str,
        images: list[Image.Image],
        model: str = MODEL_ANALYSIS,
    ) -> str:
        """画像付きテキスト分析（参照画像の構造分析等）。テキスト応答のみ返す。"""
        contents: list = []
        for img in images:
            contents.append(img)
        contents.append(prompt)
        response = self.client.models.generate_content(
            model=model,
            contents=contents,
        )
        return response.text

    def generate_image(
        self,
        prompt: str,
        reference_images: list[Image.Image] | None = None,
        aspect_ratio: str = "16:9",
        image_size: str = "2K",
        model: str = MODEL_IMAGE,
    ) -> tuple[Image.Image | None, str | None]:
        """
        画像を生成する。
        参照画像（スタイルトランスファー用）はPIL Imageのリストで渡す。

        Returns:
            (生成画像, レスポンステキスト) のタプル
        """
        # 参照画像 → プロンプトの順でcontentsを組み立て
        # （参照画像を先に見せてからテキスト指示を与えることでスタイル模倣が効きやすくなる）
        contents: list = []
        if reference_images:
            for ref_img in reference_images:
                contents.append(ref_img)
        contents.append(prompt)

        # アスペクト比とサイズのバリデーション
        if aspect_ratio not in SUPPORTED_ASPECT_RATIOS:
            aspect_ratio = "16:9"
        if image_size not in SUPPORTED_IMAGE_SIZES:
            image_size = "2K"

        response = self.client.models.generate_content(
            model=model,
            contents=contents,
            config=types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"],
                image_config=types.ImageConfig(
                    aspect_ratio=aspect_ratio,
                ),
            ),
        )

        generated_image = None
        response_text = None

        if response.parts:
            for part in response.parts:
                if part.text is not None:
                    response_text = part.text
                elif part.inline_data is not None:
                    genai_img = part.as_image()
                    # genai.types.Image → PIL.Image に変換
                    generated_image = Image.open(io.BytesIO(genai_img.image_bytes))

        return generated_image, response_text

    def generate_image_bytes(
        self,
        prompt: str,
        reference_images: list[Image.Image] | None = None,
        aspect_ratio: str = "16:9",
        image_size: str = "2K",
        model: str = MODEL_IMAGE,
        format: str = "PNG",
    ) -> tuple[bytes | None, str | None]:
        """画像をbytes形式で返す（Streamlitでの表示・DL用）"""
        image, text = self.generate_image(
            prompt=prompt,
            reference_images=reference_images,
            aspect_ratio=aspect_ratio,
            image_size=image_size,
            model=model,
        )

        if image is None:
            return None, text

        buf = io.BytesIO()
        image.save(buf, format=format)
        return buf.getvalue(), text
