"""
画像生成プロバイダの切替ファクトリ。

UI / 環境変数で選んだプロバイダ ('gemini' / 'openai') に応じて、
GeminiClient または OpenAIImageClient を返す。

GeminiClient.generate_image / generate_image_bytes と同じインターフェースなので、
呼び出し側は返り値のクライアントをそのまま使える。
"""

from __future__ import annotations

from typing import Literal, Protocol

from PIL import Image


PROVIDER_GEMINI = "gemini"
PROVIDER_OPENAI = "openai"

ProviderName = Literal["gemini", "openai"]


class ImageGenProtocol(Protocol):
    """GeminiClient / OpenAIImageClient が満たすインターフェース"""

    def generate_image(
        self,
        prompt: str,
        reference_images: list[Image.Image] | None = ...,
        aspect_ratio: str = ...,
        image_size: str = ...,
    ) -> tuple[Image.Image | None, str | None]: ...

    def generate_image_bytes(
        self,
        prompt: str,
        reference_images: list[Image.Image] | None = ...,
        aspect_ratio: str = ...,
        image_size: str = ...,
        format: str = ...,
    ) -> tuple[bytes | None, str | None]: ...


def get_image_client(
    provider: str,
    gemini_api_key: str = "",
    openai_api_key: str = "",
) -> ImageGenProtocol:
    """
    プロバイダ名から画像生成クライアントを返す。

    Args:
        provider: "gemini" or "openai"
        gemini_api_key: Gemini を使う場合のキー
        openai_api_key: OpenAI を使う場合のキー

    Raises:
        ValueError: プロバイダ名が不明 or 該当プロバイダのAPIキーが未設定
    """
    p = (provider or PROVIDER_GEMINI).lower()

    if p == PROVIDER_OPENAI:
        if not openai_api_key:
            raise ValueError(
                "OpenAI を選択しましたが OPENAI_API_KEY が設定されていません。"
                "プロジェクト直下の .env を確認してください。"
            )
        from lib.openai_image_client import OpenAIImageClient
        return OpenAIImageClient(api_key=openai_api_key)

    if p == PROVIDER_GEMINI:
        if not gemini_api_key:
            raise ValueError(
                "Gemini を選択しましたが GEMINI_API_KEY が設定されていません。"
            )
        from lib.gemini_client import GeminiClient
        return GeminiClient(api_key=gemini_api_key)

    raise ValueError(f"不明なプロバイダ: {provider!r} (gemini / openai のみ対応)")


def provider_label(provider: str) -> str:
    """UI 表示用の人間に分かるラベル"""
    p = (provider or "").lower()
    if p == PROVIDER_OPENAI:
        return "OpenAI (gpt-image-2)"
    return "Gemini (gemini-3-pro-image-preview)"
