"""
プリセット画像の管理モジュール
テイスト（イラストスタイル）とレイアウト（構成パターン）の参照画像を管理する。
「おまかせ」モードではGeminiが記事内容に最適なプリセットを自動選択する。
"""

from __future__ import annotations

from PIL import Image
from lib.storage import StorageBackend


# レイアウトタイプと内部ディレクトリ名のマッピング
LAYOUT_TYPE_MAP = {
    "分類型": "classification",
    "比較型": "comparison",
    "フロー型": "flow",
    "ピラミッド型": "pyramid",
    "アイコン軽量型": "icon_light",
}

# デフォルトのテイストカテゴリ
DEFAULT_TASTE_CATEGORIES = [
    {
        "id": "flat_minimal",
        "name": "フラットミニマル",
        "description": "シンプルな線画 + フラット塗り。清潔感のあるビジネス向け",
    },
    {
        "id": "soft_illustration",
        "name": "ソフトイラスト",
        "description": "丸みのある柔らかいタッチ。親しみやすい印象",
    },
    {
        "id": "corporate_clean",
        "name": "コーポレートクリーン",
        "description": "直線的でシャープなデザイン。信頼感を演出",
    },
]

# デフォルトのレイアウトカテゴリ
DEFAULT_LAYOUT_CATEGORIES = [
    {
        "id": "classification",
        "name": "分類型",
        "description": "横3/横4/2×2のグリッドで項目を整理",
    },
    {
        "id": "comparison",
        "name": "比較型",
        "description": "左右2分割でA vs Bを対比",
    },
    {
        "id": "flow",
        "name": "フロー型",
        "description": "横ステップで流れ・順番を表現",
    },
    {
        "id": "pyramid",
        "name": "ピラミッド型",
        "description": "階層構造で優先度・重要度を表現",
    },
    {
        "id": "icon_light",
        "name": "アイコン軽量型",
        "description": "アイコン＋最小テキストで5項目以上を網羅",
    },
]

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")


class PresetManager:
    """プリセット画像の管理"""

    def __init__(self, storage: StorageBackend):
        self.storage = storage

    def list_taste_categories(self) -> list[dict]:
        """テイストカテゴリ一覧（画像数付き）"""
        categories = []
        for cat in DEFAULT_TASTE_CATEGORIES:
            prefix = f"taste/{cat['id']}"
            images = self._list_images(prefix)
            categories.append({
                **cat,
                "image_count": len(images),
                "image_keys": images,
            })

        # カスタムカテゴリ
        custom_prefix = "taste/custom"
        custom_images = self._list_images(custom_prefix)
        if custom_images:
            categories.append({
                "id": "custom",
                "name": "カスタム",
                "description": "ユーザーがアップロードしたスタイル",
                "image_count": len(custom_images),
                "image_keys": custom_images,
            })

        return categories

    def list_layout_categories(self) -> list[dict]:
        """レイアウトカテゴリ一覧（画像数付き）"""
        categories = []
        for cat in DEFAULT_LAYOUT_CATEGORIES:
            prefix = f"layout/{cat['id']}"
            images = self._list_images(prefix)
            categories.append({
                **cat,
                "image_count": len(images),
                "image_keys": images,
            })

        # カスタムカテゴリ
        custom_prefix = "layout/custom"
        custom_images = self._list_images(custom_prefix)
        if custom_images:
            categories.append({
                "id": "custom",
                "name": "カスタム",
                "description": "ユーザーがアップロードしたレイアウト",
                "image_count": len(custom_images),
                "image_keys": custom_images,
            })

        return categories

    def get_images(self, category_type: str, category_id: str) -> list[Image.Image]:
        """
        指定カテゴリの参照画像をPIL Imageリストで返す。

        Args:
            category_type: "taste" or "layout"
            category_id: カテゴリID（例: "flat_minimal", "comparison"）
        """
        prefix = f"{category_type}/{category_id}"
        image_keys = self._list_images(prefix)
        images = []
        for key in image_keys:
            try:
                data = self.storage.load(key)
                from io import BytesIO
                img = Image.open(BytesIO(data))
                images.append(img)
            except Exception:
                continue
        return images

    def get_image_thumbnails(self, category_type: str, category_id: str, size: tuple = (200, 200)) -> list[tuple[str, bytes]]:
        """サムネイル表示用: (キー, バイト列) のリストを返す"""
        prefix = f"{category_type}/{category_id}"
        image_keys = self._list_images(prefix)
        thumbnails = []
        for key in image_keys:
            try:
                data = self.storage.load(key)
                thumbnails.append((key, data))
            except Exception:
                continue
        return thumbnails

    def upload_image(self, category_type: str, category_id: str, filename: str, data: bytes) -> str:
        """プリセット画像をアップロード"""
        key = f"{category_type}/{category_id}/{filename}"
        self.storage.save(key, data)
        return key

    def delete_image(self, key: str) -> None:
        """プリセット画像を削除"""
        self.storage.delete(key)

    def get_layout_id_for_type(self, layout_type: str) -> str:
        """日本語レイアウトタイプ名から内部IDを返す"""
        return LAYOUT_TYPE_MAP.get(layout_type, "classification")

    def auto_select_taste(self, article_summary: str, gemini_client) -> str:
        """
        記事内容に最適なテイストをGeminiで自動選択する。

        Returns:
            カテゴリID（例: "flat_minimal"）
        """
        categories = self.list_taste_categories()
        cat_descriptions = "\n".join(
            f"- {c['id']}: {c['name']} - {c['description']}"
            for c in categories
            if c["image_count"] > 0
        )

        if not cat_descriptions:
            return "flat_minimal"

        prompt = f"""以下のイラストスタイルカテゴリから、この記事に最適なものを1つ選んでください。

カテゴリ:
{cat_descriptions}

記事の概要:
{article_summary[:500]}

カテゴリIDのみを返してください（例: flat_minimal）。他の文字は不要です。"""

        try:
            response = gemini_client.analyze_text(prompt)
            taste_id = response.strip().lower().replace(" ", "_")
            valid_ids = [c["id"] for c in categories]
            if taste_id in valid_ids:
                return taste_id
        except Exception:
            pass

        return "flat_minimal"

    def _list_images(self, prefix: str) -> list[str]:
        """指定プレフィックス内の画像ファイルキー一覧"""
        all_keys = self.storage.list_keys(prefix=prefix)
        return [
            k for k in all_keys
            if any(k.lower().endswith(ext) for ext in IMAGE_EXTENSIONS)
        ]
