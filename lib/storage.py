"""
ストレージ抽象層
全ファイルI/OはこのBackend経由で行い、ローカルパスに直接依存しない。
LocalStorage / GoogleDriveStorage を環境変数で切り替え可能。
"""

from __future__ import annotations

import io
import json
import os
from abc import ABC, abstractmethod
from pathlib import Path
import shutil


class StorageBackend(ABC):
    """ストレージバックエンドの抽象クラス"""

    @abstractmethod
    def save(self, key: str, data: bytes) -> str:
        """データを保存し、キーを返す"""
        ...

    @abstractmethod
    def load(self, key: str) -> bytes:
        """キーからデータを読み込む"""
        ...

    @abstractmethod
    def load_text(self, key: str, encoding: str = "utf-8") -> str:
        """キーからテキストデータを読み込む"""
        ...

    @abstractmethod
    def save_text(self, key: str, text: str, encoding: str = "utf-8") -> str:
        """テキストデータを保存し、キーを返す"""
        ...

    @abstractmethod
    def list_keys(self, prefix: str = "", suffix: str = "") -> list[str]:
        """指定プレフィックス/サフィックスに一致するキー一覧を返す"""
        ...

    @abstractmethod
    def exists(self, key: str) -> bool:
        """キーが存在するか確認"""
        ...

    @abstractmethod
    def delete(self, key: str) -> None:
        """キーを削除"""
        ...


class LocalStorage(StorageBackend):
    """ローカルファイルシステムベースのストレージ"""

    def __init__(self, base_dir: str | Path):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        return self.base_dir / key

    def save(self, key: str, data: bytes) -> str:
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key

    def load(self, key: str) -> bytes:
        path = self._resolve(key)
        if not path.exists():
            raise FileNotFoundError(f"Key not found: {key}")
        return path.read_bytes()

    def load_text(self, key: str, encoding: str = "utf-8") -> str:
        path = self._resolve(key)
        if not path.exists():
            raise FileNotFoundError(f"Key not found: {key}")
        return path.read_text(encoding=encoding)

    def save_text(self, key: str, text: str, encoding: str = "utf-8") -> str:
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding=encoding)
        return key

    def list_keys(self, prefix: str = "", suffix: str = "") -> list[str]:
        results = []
        search_dir = self._resolve(prefix) if prefix else self.base_dir
        if not search_dir.exists():
            return results
        if search_dir.is_file():
            rel = str(search_dir.relative_to(self.base_dir))
            if rel.endswith(suffix):
                return [rel]
            return []
        for path in search_dir.rglob("*"):
            if path.is_file():
                rel = str(path.relative_to(self.base_dir))
                if rel.endswith(suffix):
                    results.append(rel)
        return sorted(results)

    def exists(self, key: str) -> bool:
        return self._resolve(key).exists()

    def delete(self, key: str) -> None:
        path = self._resolve(key)
        if path.is_file():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)

    def get_absolute_path(self, key: str) -> Path:
        """ローカル固有: 絶対パスを返す（Pillow等に渡す用）"""
        return self._resolve(key)


class GoogleDriveStorage(StorageBackend):
    """
    Google Drive ベースのストレージ。
    サービスアカウント認証で共有ドライブのフォルダにアクセスする。

    必要な環境変数:
        GOOGLE_DRIVE_FOLDER_ID: ルートフォルダID
        GOOGLE_SERVICE_ACCOUNT_JSON: サービスアカウントキーJSON文字列
          or
        GOOGLE_SERVICE_ACCOUNT_FILE: サービスアカウントキーファイルのパス
    """

    SCOPES = ["https://www.googleapis.com/auth/drive"]

    def __init__(self, folder_id: str, credentials_json: str | None = None, credentials_file: str | None = None):
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        # 認証情報の取得
        if credentials_json:
            info = json.loads(credentials_json)
            creds = service_account.Credentials.from_service_account_info(info, scopes=self.SCOPES)
        elif credentials_file:
            creds = service_account.Credentials.from_service_account_file(credentials_file, scopes=self.SCOPES)
        else:
            raise ValueError("credentials_json or credentials_file が必要です")

        # Streamlit CloudでSSLエラーが出るため、certifiのCA証明書を明示指定
        import httplib2
        import certifi
        from google_auth_httplib2 import AuthorizedHttp

        http = httplib2.Http(ca_certs=certifi.where())
        authed_http = AuthorizedHttp(creds, http=http)
        self.service = build("drive", "v3", http=authed_http)
        self.root_folder_id = folder_id
        # フォルダIDキャッシュ: パス文字列 → Drive folder ID
        self._folder_cache: dict[str, str] = {"": self.root_folder_id}

    def _get_or_create_folder(self, folder_path: str) -> str:
        """パス文字列（例: "site/ref_images/mv"）に対応するDriveフォルダIDを取得or作成"""
        if folder_path in self._folder_cache:
            return self._folder_cache[folder_path]

        parts = folder_path.split("/")
        current_path = ""
        parent_id = self.root_folder_id

        for part in parts:
            current_path = f"{current_path}/{part}" if current_path else part
            if current_path in self._folder_cache:
                parent_id = self._folder_cache[current_path]
                continue

            # 既存フォルダを検索
            query = (
                f"name='{part}' and '{parent_id}' in parents "
                f"and mimeType='application/vnd.google-apps.folder' and trashed=false"
            )
            results = self.service.files().list(
                q=query, fields="files(id, name)", spaces="drive",
                supportsAllDrives=True, includeItemsFromAllDrives=True,
            ).execute()
            files = results.get("files", [])

            if files:
                parent_id = files[0]["id"]
            else:
                # フォルダ作成
                meta = {
                    "name": part,
                    "mimeType": "application/vnd.google-apps.folder",
                    "parents": [parent_id],
                }
                folder = self.service.files().create(
                    body=meta, fields="id",
                    supportsAllDrives=True,
                ).execute()
                parent_id = folder["id"]

            self._folder_cache[current_path] = parent_id

        return parent_id

    def _find_file(self, key: str) -> str | None:
        """keyに対応するDriveファイルIDを返す。なければNone"""
        parent_path = "/".join(key.split("/")[:-1])
        filename = key.split("/")[-1]

        # 親フォルダが存在するか確認（作成はしない）
        parent_id = self._folder_cache.get(parent_path)
        if parent_id is None:
            # キャッシュにない場合、ルートから辿って探す
            try:
                parent_id = self._resolve_folder(parent_path)
            except FileNotFoundError:
                return None

        query = (
            f"name='{filename}' and '{parent_id}' in parents "
            f"and mimeType!='application/vnd.google-apps.folder' and trashed=false"
        )
        results = self.service.files().list(
            q=query, fields="files(id)", spaces="drive",
            supportsAllDrives=True, includeItemsFromAllDrives=True,
        ).execute()
        files = results.get("files", [])
        return files[0]["id"] if files else None

    def _resolve_folder(self, folder_path: str) -> str:
        """既存フォルダを検索のみ（作成しない）。なければFileNotFoundError"""
        if not folder_path:
            return self.root_folder_id
        if folder_path in self._folder_cache:
            return self._folder_cache[folder_path]

        parts = folder_path.split("/")
        current_path = ""
        parent_id = self.root_folder_id

        for part in parts:
            current_path = f"{current_path}/{part}" if current_path else part
            if current_path in self._folder_cache:
                parent_id = self._folder_cache[current_path]
                continue

            query = (
                f"name='{part}' and '{parent_id}' in parents "
                f"and mimeType='application/vnd.google-apps.folder' and trashed=false"
            )
            results = self.service.files().list(
                q=query, fields="files(id)", spaces="drive",
                supportsAllDrives=True, includeItemsFromAllDrives=True,
            ).execute()
            files = results.get("files", [])
            if not files:
                raise FileNotFoundError(f"Folder not found: {folder_path}")
            parent_id = files[0]["id"]
            self._folder_cache[current_path] = parent_id

        return parent_id

    def save(self, key: str, data: bytes) -> str:
        """バイナリデータをDriveに保存"""
        from googleapiclient.http import MediaIoBaseUpload

        parent_path = "/".join(key.split("/")[:-1])
        filename = key.split("/")[-1]
        parent_id = self._get_or_create_folder(parent_path) if parent_path else self.root_folder_id

        # 既存ファイルがあれば上書き
        existing_id = self._find_file(key)
        media = MediaIoBaseUpload(io.BytesIO(data), mimetype="application/octet-stream", resumable=True)

        if existing_id:
            self.service.files().update(
                fileId=existing_id, media_body=media,
                supportsAllDrives=True,
            ).execute()
        else:
            meta = {"name": filename, "parents": [parent_id]}
            self.service.files().create(
                body=meta, media_body=media, fields="id",
                supportsAllDrives=True,
            ).execute()
        return key

    def load(self, key: str) -> bytes:
        """Driveからバイナリデータを読み込む"""
        file_id = self._find_file(key)
        if not file_id:
            raise FileNotFoundError(f"Key not found: {key}")
        content = self.service.files().get_media(
            fileId=file_id, supportsAllDrives=True,
        ).execute()
        return content

    def load_text(self, key: str, encoding: str = "utf-8") -> str:
        return self.load(key).decode(encoding)

    def save_text(self, key: str, text: str, encoding: str = "utf-8") -> str:
        return self.save(key, text.encode(encoding))

    def list_keys(self, prefix: str = "", suffix: str = "") -> list[str]:
        """prefix配下の全ファイルを再帰的にリストアップ"""
        results: list[str] = []
        # 末尾スラッシュを除去（Driveフォルダ検索で空パーツになるのを防止）
        prefix = prefix.rstrip("/")
        try:
            folder_id = self._resolve_folder(prefix) if prefix else self.root_folder_id
        except FileNotFoundError:
            return results
        self._list_recursive(folder_id, prefix, suffix, results)
        return sorted(results)

    def _list_recursive(self, folder_id: str, current_prefix: str, suffix: str, results: list[str]) -> None:
        """フォルダを再帰的に走査"""
        page_token = None
        while True:
            query = f"'{folder_id}' in parents and trashed=false"
            resp = self.service.files().list(
                q=query, fields="nextPageToken, files(id, name, mimeType)",
                spaces="drive", pageToken=page_token,
                supportsAllDrives=True, includeItemsFromAllDrives=True,
            ).execute()

            for f in resp.get("files", []):
                path = f"{current_prefix}/{f['name']}" if current_prefix else f["name"]
                if f["mimeType"] == "application/vnd.google-apps.folder":
                    self._list_recursive(f["id"], path, suffix, results)
                else:
                    if path.endswith(suffix):
                        results.append(path)

            page_token = resp.get("nextPageToken")
            if not page_token:
                break

    def exists(self, key: str) -> bool:
        return self._find_file(key) is not None

    def delete(self, key: str) -> None:
        """ファイルをゴミ箱に移動（完全削除はしない）"""
        file_id = self._find_file(key)
        if file_id:
            self.service.files().update(
                fileId=file_id, body={"trashed": True},
                supportsAllDrives=True,
            ).execute()
