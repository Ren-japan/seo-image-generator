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
    # サイト参照画像の管理（カテゴリ別: article / mv）
    # =============================================

    # サポートされる参照画像カテゴリ
    REF_IMAGE_CATEGORIES = ["article", "mv"]

    def _ref_images_prefix(self, site_name: str, category: str = "article", preset_id: str | None = None) -> str:
        if category == "mv" and preset_id:
            return f"{site_name}_ref_images/mv/{preset_id}/"
        return f"{site_name}_ref_images/{category}/"

    def _migrate_legacy_ref_images(self, site_name: str) -> None:
        """旧形式（カテゴリなし）の参照画像をarticleカテゴリに移行"""
        legacy_prefix = f"{site_name}_ref_images/"
        keys = self.storage.list_keys(prefix=legacy_prefix)
        for key in keys:
            # すでにカテゴリ付きのパスならスキップ
            relative = key[len(legacy_prefix):]
            if "/" in relative:
                continue
            # 旧形式 → article/ に移動
            new_key = f"{legacy_prefix}article/{relative}"
            try:
                data = self.storage.load(key)
                self.storage.save(new_key, data)
                self.storage.delete(key)
            except Exception:
                continue

    def add_reference_image(self, site_name: str, filename: str, data: bytes, category: str = "article", preset_id: str | None = None) -> str:
        """参照画像を追加し、storage key を返す"""
        key = f"{self._ref_images_prefix(site_name, category, preset_id)}{filename}"
        self.storage.save(key, data)
        return key

    def list_reference_images(self, site_name: str, category: str = "article", preset_id: str | None = None) -> list[str]:
        """サイトの参照画像キー一覧を返す（カテゴリ指定、MV時はpreset_id指定可）"""
        # 初回呼び出し時に旧形式のマイグレーションを実行
        self._migrate_legacy_ref_images(site_name)
        prefix = self._ref_images_prefix(site_name, category, preset_id)
        return self.storage.list_keys(prefix=prefix)

    def load_reference_image(self, key: str) -> bytes:
        """参照画像のバイナリを読み込む"""
        return self.storage.load(key)

    def delete_reference_image(self, key: str) -> None:
        """参照画像を削除"""
        self.storage.delete(key)

    def get_reference_pil_images(self, site_name: str, category: str = "article", preset_id: str | None = None) -> list:
        """サイトの参照画像をPIL Imageのリストで返す（最大5枚）"""
        from PIL import Image
        import io
        keys = self.list_reference_images(site_name, category, preset_id)
        images = []
        for key in keys[:5]:  # 最大5枚制限
            try:
                data = self.storage.load(key)
                img = Image.open(io.BytesIO(data))
                images.append(img)
            except Exception:
                continue
        return images

    def analyze_reference_images(self, site_name: str, gemini_client, category: str = "article", preset_id: str | None = None) -> str:
        """参照画像をGeminiで分析し、共通デザイン特徴を抽出する"""
        images = self.get_reference_pil_images(site_name, category, preset_id)
        if not images:
            return ""

        if category == "mv":
            prompt = """以下の画像はすべて同一サイトで使用されているMV（メインビジュアル/アイキャッチ）画像です。
画像生成AIに「これと同じデザインで中身だけ変えて」と指示するための、超具体的なデザイン仕様書を作成してください。

以下のスロットごとに、位置・サイズ・フォント・装飾・色をすべて数値レベルで記述してください。

== スロット別の分析項目 ==

1. **背景**
   - 上部と下部の色（HEXコード推定）
   - グラデーションの方向・境界線の角度
   - 上部カラーエリアと下部白エリアの面積比率（例: 60:40）
   - テクスチャやノイズの有無

2. **煽りテキスト（左上の小さいテキスト）**
   - 画像内での位置（左上からの距離を%で推定）
   - フォントサイズ感（画像幅に対する比率）
   - フォントの太さ（regular/bold/extra-bold）
   - 文字色（HEXコード推定）
   - 装飾（囲み、吹き出し、下線、背景色の有無とその詳細）

3. **メインタイトル（最も大きいテキスト）**
   - 画像内での位置
   - 画像面積に対するテキスト占有率（%で推定）
   - フォントサイズ感（画像幅に対する比率）
   - フォントの太さ
   - 文字色（HEXコード推定）
   - 縁取りの有無・色・太さ（px推定）
   - ドロップシャドウの有無・色・方向・ぼかし
   - 立体感の表現方法（二重縁取り、エンボス等）
   - 改行位置・行間

4. **サブタイトル（メインタイトルの下のテキスト）**
   - 画像内での位置
   - フォントサイズ感（メインタイトルとの比率）
   - フォントの太さ
   - 文字色（HEXコード推定）
   - 縁取りの有無・色・太さ
   - その他装飾

5. **帯テキスト（横長の帯の上のテキスト）**
   - 帯の色（HEXコード推定）
   - 帯の形状（角丸?直角?）、高さ、幅（画像幅に対する%）
   - 帯の位置（画像内のどの位置）
   - テキストの色・サイズ・太さ
   - 帯の影や枠線の有無

6. **補足テキスト（下部の小さいテキスト）**
   - 画像内での位置
   - フォントサイズ感
   - 文字色
   - 装飾の有無

7. **メイン人物（右側の人物）**
   - 画像内での位置（右下?右中央?）
   - 画像面積に対する占有率（%）
   - 人物のスタイル（実写風/イラスト風/アニメ風）
   - 頭身、体型、描き込みの密度
   - 人物と背景の関係（切り抜き風?背景に溶け込み?）
   - 人物にかかる影やグロー効果

8. **全体のレイアウトバランス**
   - テキストエリアと人物エリアの左右比率
   - 上下左右のマージン（画像サイズに対する%）
   - 要素間の間隔の傾向（密/普通/疎）
   - 視線誘導の流れ

== 分析時の注意（よくある誤認を防ぐ） ==
- テキストの水平位置を正確に判定すること。テキストの左端が画像幅の30%より左にあれば「左寄せ」、30-70%なら「中央揃え」、70%より右なら「右寄せ」。安易に「中央に揃える」と書かないこと
- テキストの色を正確に判定すること。赤い文字を暗い色と誤認しないこと。彩度の高い色（赤、青、緑など）はそのまま報告すること
- 同じ行のテキスト内で色が変わっている場合（例：一部だけ赤い）、それを明記すること。「白 or 赤」のような曖昧な記述ではなく「基本は白、一部のキーワードが赤」と具体的に書くこと
- 縁取りは「ある」か「ない」かを画像をよく見て判定し、ある場合は色と推定太さを必ず記載すること
- 人物が実写写真かイラストかを正確に判定すること。写実的な人物（肌のテクスチャ、毛髪の細部が見える）は「実写写真」と判定する

== 出力ルール ==
- 各項目を「〜にする」という断定形の指示文で書く
- HEXカラーコードは必ず推定して記載する
- サイズ・位置は画像サイズに対する%で記載する
- 曖昧な表現（「大きめ」「やや左」）は使わず、具体的な数値・比率で書く
- 「AまたはB」のような曖昧な記述は禁止。画像をよく観察して1つに断定すること
- 画像生成AIへのプロンプトにそのままコピペできる形式にする"""
        else:
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

    def analyze_mv_slot_structure(self, site_name: str, gemini_client, preset_id: str | None = None) -> dict:
        """MV参照画像からテキストスロット構造をGemini Flashで自動検出しJSONで返す。

        Returns:
            {
                "slots": [
                    {"role": "hook"|"main_title"|"subtitle"|"band_text"|"supplement_text",
                     "description": "スタイルの短い説明"},
                    ...
                ],
                "absent_slots": ["subtitle", "supplement_text"],
                "person_style": "背景込み実写 / 切り抜き写真 / イラスト等",
                "background_summary": "背景の構造を短く説明"
            }
        """
        import json as _json

        images = self.get_reference_pil_images(site_name, category="mv", preset_id=preset_id)
        if not images:
            return {}

        prompt = """以下のMV（メインビジュアル/アイキャッチ）参照画像を分析し、テキストスロットの構造をJSON形式で抽出してください。

== 分析ルール ==
1. 画像内に存在するテキスト要素を**上から順に**全て列挙する
2. 各テキスト要素の役割を以下の5種類のいずれかに分類する:
   - hook: 煽りテキスト（短いフレーズ。ピル/バッジの中にある場合もプレーンテキストの場合もある）
   - main_title: メインタイトル（最も大きいテキスト）
   - subtitle: サブタイトル（メインタイトルの補足的なテキスト）
   - band_text: 帯テキスト（色付きの帯やボックス内のテキスト）
   - supplement_text: 補足テキスト（下部の小さいテキスト）
3. 各要素のスタイルを簡潔に記述する（色、太さ、装飾、背景の有無）
4. **5枚全てに共通する要素だけ**を抽出する。1枚だけにある要素は無視する
5. 5枚のどれにも存在しないスロットは absent_slots に列挙する
6. 人物のスタイル（切り抜き/背景込み写真/イラスト）を判定する
7. 背景の構造を簡潔に記述する

== 特に注意 ==
- 各roleは最大1つ。改行でテキストが2行になっていても1つのスロットとして扱う（main_titleが複数行でも1エントリ）
- テキストが帯/ピル/バッジの中にあるか、プレーンテキストかを正確に判定する
- 文字の縁取り（outline）の有無を正確に判定する
- 文字色を正確に判定する（白/黒/テーマカラー/赤等）
- ロゴやアイコンはテキストスロットに含めない

== 出力形式（JSON） ==
```json
{
  "slots": [
    {"role": "hook", "description": "スタイルの短い説明（位置・色・太さ・装飾）"},
    {"role": "band_text", "description": "..."},
    {"role": "main_title", "description": "..."}
  ],
  "absent_slots": ["subtitle", "supplement_text"],
  "person_style": "背景込み実写（切り抜きではない）",
  "background_summary": "左に白い直角カード（薄い影）、右に人物の背景ボケ写真"
}
```

slotsは画像内の上から順に記載すること。JSON以外のテキストは出力しないこと。"""

        response_text = gemini_client.analyze_with_images(prompt, images)

        # JSONを抽出してパース
        try:
            import re
            json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", response_text, re.DOTALL)
            if json_match:
                result = _json.loads(json_match.group(1))
            else:
                result = _json.loads(response_text)

            # 後処理: 同じroleの重複を除去（最初の1つを残す）
            if "slots" in result:
                seen_roles = set()
                deduped = []
                for s in result["slots"]:
                    role = s.get("role", "")
                    if role not in seen_roles:
                        seen_roles.add(role)
                        deduped.append(s)
                result["slots"] = deduped

            return result
        except (_json.JSONDecodeError, AttributeError):
            return {}
