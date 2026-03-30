# Google Drive ストレージ セットアップガイド

SEO Image Generator で生成した画像を Google 共有ドライブに自動保存するためのセットアップ手順。

## 前提条件

- Google Workspace 契約済みアカウント（共有ドライブが使える）
- Google Cloud Console へのアクセス権

---

## Step 1: GCP プロジェクト作成

1. [Google Cloud Console](https://console.cloud.google.com/) にログイン
2. 上部の「プロジェクトの選択」→「新しいプロジェクト」
3. プロジェクト名: `seo-image-generator`（任意）
4. 組織: 自分の Workspace ドメインを選択
5. 「作成」をクリック

## Step 2: Google Drive API を有効化

1. 作成したプロジェクトを選択した状態で
2. 「APIとサービス」→「ライブラリ」→「Google Drive API」を検索
3. 「有効にする」をクリック

直接URL: `https://console.cloud.google.com/apis/library/drive.googleapis.com?project=YOUR_PROJECT_ID`

## Step 3: サービスアカウント作成

1. 「APIとサービス」→「認証情報」→「+ 認証情報を作成」→「サービスアカウント」
2. サービスアカウント名: `drive-storage`（任意）
3. 「作成して続行」→ 権限は省略でOK →「完了」

### サービスアカウントキーの作成でブロックされた場合

Google Workspace の新規組織では、セキュリティポリシー `iam.disableServiceAccountKeyCreation` がデフォルトで有効になっていて、サービスアカウントキーの作成がブロックされることがある。

**解決手順:**

1. **組織ポリシー管理者ロールを付与する**
   - GCP Console 上部のプロジェクト選択で、組織（例: `plus-msteam.com`）を選択
   - 「IAMと管理」→「IAM」
   - 自分のアカウントの鉛筆アイコン（編集）をクリック
   - 「+ 別のロールを追加」→「Organization Policy Administrator」（組織ポリシー管理者）を追加
   - 「保存」

2. **組織ポリシーを変更する**
   - 「IAMと管理」→「組織のポリシー」
   - フィルタで `disableServiceAccountKeyCreation` を検索
   - レガシー版（`iam.disableServiceAccountKeyCreation`）をクリック
   - 「ポリシーを管理」→ ルールの「適用」を **オフ** に変更
   - 「ポリシーを設定」

3. サービスアカウントの「鍵」タブに戻って「キーを追加」→「新しい鍵を作成」→ JSON

## Step 4: JSON キーをダウンロード

1. サービスアカウントの詳細ページ →「鍵」タブ
2. 「キーを追加」→「新しい鍵を作成」→ JSON を選択
3. JSON ファイルが自動ダウンロードされる
4. このファイルをプロジェクトルートに `service-account-key.json` として配置

> **注意**: このファイルは `.gitignore` に含まれているので Git にはコミットされない

## Step 5: 共有ドライブにフォルダ作成 + 権限付与

1. Google Drive で共有ドライブを開く
2. フォルダを作成（例: `SEO Image Generator`）
3. 共有ドライブの「メンバーを管理」をクリック
4. サービスアカウントのメールアドレスを追加:
   ```
   drive-storage@YOUR_PROJECT_ID.iam.gserviceaccount.com
   ```
5. 権限: 「コンテンツ管理者」または「投稿者」
6. 外部共有の確認が出たら「このまま共有」

## Step 6: .env に設定

フォルダの URL からフォルダ ID を取得:
```
https://drive.google.com/drive/folders/XXXXXXXXXXXXXXXXXXXXXXXXXX
                                       ↑ これがフォルダID
```

`.env` に追加:
```
GOOGLE_DRIVE_FOLDER_ID=XXXXXXXXXXXXXXXXXXXXXXXXXX
GOOGLE_SERVICE_ACCOUNT_FILE=service-account-key.json
```

---

## 動作確認

Streamlit を起動して画像を生成すると、共有ドライブに以下の構造で自動保存される:

```
SEO Image Generator/
├── {サイト名}.json              ← サイト設定
├── {サイト名}_ref_images/       ← 参照画像
│   ├── article/
│   └── mv/
└── generated/                   ← 生成画像（自動保存）
    └── {サイト名}/
        ├── article/
        │   └── 2026-03-30_153000_見出しテキスト.png
        └── mv/
            └── 2026-03-30_153000_メインタイトル.png
```

フォルダは画像生成時に自動作成されるので、手動でフォルダを作る必要はない。

## Streamlit Cloud にデプロイする場合

`.env` ではなく Streamlit の Secrets を使う:

1. Streamlit Cloud の「Settings」→「Secrets」
2. 以下を追加:
```toml
GOOGLE_DRIVE_FOLDER_ID = "XXXXXXXXXXXXXXXXXXXXXXXXXX"
GOOGLE_SERVICE_ACCOUNT_JSON = '{"type":"service_account","project_id":"...", ...}'
```

`GOOGLE_SERVICE_ACCOUNT_JSON` には JSON キーファイルの中身をそのまま1行で貼り付ける。
