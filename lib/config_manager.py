"""
サイト設定の管理（JSON永続化）
各サイトのデザインシステム・カラーパレット・画像サイズ等を管理する。
"""

from __future__ import annotations

import json
from lib.storage import StorageBackend


DEFAULT_CONFIG = {
    "brand_name": "",
    "site_url": "",
    "brand_tone": "professional and approachable",
    "language": "Japanese",
    # カラーパレット
    "primary_color": "#3B82F6",
    "secondary_color": "#10B981",
    "accent_color": "#F59E0B",
    "background_color": "#FFFFFF",
    "text_color": "#1F2937",
    "danger_color": "#E74A3B",
    # イラストスタイル
    "illustration_style": "flat minimal",
    "line_weight": "2.8〜3.2px統一の安定感のあるベクター線画",
    "character_style": "4頭身前後、点の目＋小さな口の記号的表現",
    "fill_style": "フラット塗り（影・ハイライト・立体感なし）",
    # フォント
    "font_family": "Noto Sans JP Medium",
    # レイアウト
    "card_style": "白背景(#FFFFFF) + 角丸28px + 極薄枠線(1px)",
    "spacing": "広めに均等（詰め込み禁止）",
    # 画像サイズ
    "image_sizes": {
        "article": {"width": 886, "height": 600, "label": "記事内画像"},
        "mv": {"width": 1200, "height": 630, "label": "MV/アイキャッチ"},
        "ogp": {"width": 1200, "height": 630, "label": "OGP画像"},
    },
    # レイアウトタイプ
    "layout_types": [
        "分類型", "比較型", "フロー型", "ピラミッド型", "アイコン軽量型"
    ],
    # 禁止事項
    "prohibited_elements": (
        "- 手書き風、クレヨン風、水彩風のタッチ\n"
        "- 3D、ドロップシャドウ、グラデーションの使用\n"
        "- 指定色以外の使用\n"
        "- 説明文の長文化\n"
        "- 抽象的な背景パターンの挿入"
    ),
    "additional_notes": "",
    # ロゴ
    "logo_key": "",
    "logo_position": "bottom-right",
    "logo_size_pct": 0.08,
}


class ConfigManager:
    """サイト設定のCRUD管理"""

    def __init__(self, storage: StorageBackend):
        self.storage = storage
        self._ensure_default()

    def _ensure_default(self):
        """デフォルト設定が存在しなければ作成"""
        if not self.storage.exists("_default.json"):
            self.storage.save_text(
                "_default.json",
                json.dumps(DEFAULT_CONFIG, ensure_ascii=False, indent=2),
            )

    def list_sites(self) -> list[str]:
        """登録済みサイト名一覧を返す"""
        keys = self.storage.list_keys(suffix=".json")
        return [
            k.replace(".json", "")
            for k in keys
            if k != "_default.json"
        ]

    def load(self, site_name: str) -> dict:
        """サイト設定を読み込む。存在しなければデフォルトを返す"""
        key = f"{site_name}.json"
        if self.storage.exists(key):
            text = self.storage.load_text(key)
            return json.loads(text)
        # デフォルトをベースにする
        default_text = self.storage.load_text("_default.json")
        return json.loads(default_text)

    def save(self, site_name: str, config: dict) -> None:
        """サイト設定を保存"""
        key = f"{site_name}.json"
        self.storage.save_text(
            key,
            json.dumps(config, ensure_ascii=False, indent=2),
        )

    def delete(self, site_name: str) -> None:
        """サイト設定を削除"""
        key = f"{site_name}.json"
        if self.storage.exists(key):
            self.storage.delete(key)

    def get_default(self) -> dict:
        """デフォルト設定のコピーを返す"""
        return DEFAULT_CONFIG.copy()

    # =============================================
    # サイト参照画像の管理
    # =============================================

    def _ref_images_prefix(self, site_name: str) -> str:
        return f"{site_name}_ref_images/"

    def add_reference_image(self, site_name: str, filename: str, data: bytes) -> str:
        """参照画像を追加し、storage key を返す"""
        key = f"{self._ref_images_prefix(site_name)}{filename}"
        self.storage.save(key, data)
        return key

    def list_reference_images(self, site_name: str) -> list[str]:
        """サイトの参照画像キー一覧を返す"""
        prefix = self._ref_images_prefix(site_name)
        return self.storage.list_keys(prefix=prefix)

    def load_reference_image(self, key: str) -> bytes:
        """参照画像のバイナリを読み込む"""
        return self.storage.load(key)

    def delete_reference_image(self, key: str) -> None:
        """参照画像を削除"""
        self.storage.delete(key)

    def get_reference_pil_images(self, site_name: str) -> list:
        """サイトの参照画像をPIL Imageのリストで返す（最大5枚）"""
        from PIL import Image
        import io
        keys = self.list_reference_images(site_name)
        images = []
        for key in keys[:5]:  # 最大5枚制限
            try:
                data = self.storage.load(key)
                img = Image.open(io.BytesIO(data))
                images.append(img)
            except Exception:
                continue
        return images

    def analyze_reference_images(self, site_name: str, gemini_client) -> str:
        """参照画像をGeminiで分析し、共通デザイン特徴を抽出する"""
        images = self.get_reference_pil_images(site_name)
        if not images:
            return ""

        prompt = """以下の画像はすべて同一サイトで使用されているインフォグラフィック画像です。
これらの画像に共通するデザイン特徴を、画像生成AIへの指示として使える形式で抽出してください。

以下の項目について具体的に記述してください：

1. **背景**: 色、グラデーションの有無、テクスチャ
2. **カード/ボックス**: 形状、角丸、枠線の色と太さ、影の有無
3. **見出し帯**: 色、形状、テキスト色、配置位置
4. **イラストの線画スタイル**: 線の太さ、均一さ、手描き感 vs ベクター感
5. **人物イラスト**: 頭身、顔の描き方（目・口の表現）、体型
6. **塗りスタイル**: フラット/グラデーション/影の有無
7. **色使いの傾向**: メインで使われている色、アクセント色、色数の制限
8. **余白**: 要素間の間隔、詰まり具合
9. **アイコン**: スタイル、サイズ感
10. **全体的な印象**: クリーン/カジュアル/フォーマル等

出力は箇条書きで、画像生成プロンプトにそのまま追加できる具体的な指示文として書いてください。
「〜のようにする」ではなく「〜にする」という断定形で書いてください。"""

        # 画像 + プロンプトを送信
        contents = [prompt] + images
        from google.genai import types
        response = gemini_client.client.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents,
        )
        return response.text if response.text else ""
