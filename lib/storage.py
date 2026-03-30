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
        from google.auth.transport.requests import AuthorizedSession

        # 認証情報の取得
        if credentials_json:
            info = json.loads(credentials_json)
            creds = service_account.Credentials.from_service_account_info(info, scopes=self.SCOPES)
        elif credentials_file:
            creds = service_account.Credentials.from_service_account_file(credentials_file, scopes=self.SCOPES)
        else:
            raise ValueError("credentials_json or credentials_file が必要です")

        # httplib2はStreamlit CloudでSSL不安定 → requestsベースのセッションを使う
        self._session = AuthorizedSession(creds)
        self._base_url = "https://www.googleapis.com/drive/v3"
        self._upload_url = "https://www.googleapis.com/upload/drive/v3"
        self.root_folder_id = folder_id
        # フォルダIDキャッシュ: パス文字列 → Drive folder ID
        self._folder_cache: dict[str, str] = {"": self.root_folder_id}

    # --- 内部ヘルパー: requests で Drive API v3 を直接叩く ---

    def _api_get(self, endpoint: str, params: dict | None = None) -> dict:
        """Drive API GETリクエスト"""
        resp = self._session.get(f"{self._base_url}/{endpoint}", params=params or {})
        resp.raise_for_status()
        return resp.json()

    def _api_post(self, endpoint: str, json_body: dict, params: dict | None = None) -> dict:
        """Drive API POSTリクエスト"""
        resp = self._session.post(f"{self._base_url}/{endpoint}", json=json_body, params=params or {})
        resp.raise_for_status()
        return resp.json()

    def _api_patch(self, endpoint: str, data: bytes, content_type: str = "application/octet-stream") -> dict:
        """Drive API PATCHリクエスト（ファイル更新）"""
        resp = self._session.patch(
            f"{self._upload_url}/{endpoint}",
            data=data,
            headers={"Content-Type": content_type},
            params={"uploadType": "media", "supportsAllDrives": "true"},
        )
        resp.raise_for_status()
        return resp.json()

    def _files_list(self, q: str, fields: str = "files(id,name,mimeType)", page_token: str | None = None) -> dict:
        """files.list をrequestsで実行"""
        params = {
            "q": q, "fields": f"nextPageToken,{fields}", "spaces": "drive",
            "supportsAllDrives": "true", "includeItemsFromAllDrives": "true",
        }
        if page_token:
            params["pageToken"] = page_token
        return self._api_get("files", params)

    def _get_or_create_folder(self, folder_path: str) -> str:
        """パス文字列に対応するDriveフォルダIDを取得or作成"""
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
            result = self._files_list(query, "files(id)")
            files = result.get("files", [])

            if files:
                parent_id = files[0]["id"]
            else:
                # フォルダ作成
                meta = {
                    "name": part,
                    "mimeType": "application/vnd.google-apps.folder",
                    "parents": [parent_id],
                }
                folder = self._api_post("files", meta, {"supportsAllDrives": "true"})
                parent_id = folder["id"]

            self._folder_cache[current_path] = parent_id

        return parent_id

    def _find_file(self, key: str) -> str | None:
        """keyに対応するDriveファイルIDを返す。なければNone"""
        parent_path = "/".join(key.split("/")[:-1])
        filename = key.split("/")[-1]

        parent_id = self._folder_cache.get(parent_path)
        if parent_id is None:
            try:
                parent_id = self._resolve_folder(parent_path)
            except FileNotFoundError:
                return None

        query = (
            f"name='{filename}' and '{parent_id}' in parents "
            f"and mimeType!='application/vnd.google-apps.folder' and trashed=false"
        )
        result = self._files_list(query, "files(id)")
        files = result.get("files", [])
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
            result = self._files_list(query, "files(id)")
            files = result.get("files", [])
            if not files:
                raise FileNotFoundError(f"Folder not found: {folder_path}")
            parent_id = files[0]["id"]
            self._folder_cache[current_path] = parent_id

        return parent_id

    def save(self, key: str, data: bytes) -> str:
        """バイナリデータをDriveに保存"""
        parent_path = "/".join(key.split("/")[:-1])
        filename = key.split("/")[-1]
        parent_id = self._get_or_create_folder(parent_path) if parent_path else self.root_folder_id

        existing_id = self._find_file(key)

        if existing_id:
            # 既存ファイル更新
            self._api_patch(f"files/{existing_id}", data)
        else:
            # 新規作成（multipartアップロード）
            import requests as req_lib
            boundary = "----DriveUploadBoundary"
            meta_json = json.dumps({"name": filename, "parents": [parent_id]})
            body = (
                f"--{boundary}\r\n"
                f"Content-Type: application/json; charset=UTF-8\r\n\r\n"
                f"{meta_json}\r\n"
                f"--{boundary}\r\n"
                f"Content-Type: application/octet-stream\r\n\r\n"
            ).encode() + data + f"\r\n--{boundary}--".encode()

            resp = self._session.post(
                f"{self._upload_url}/files",
                data=body,
                headers={"Content-Type": f"multipart/related; boundary={boundary}"},
                params={"uploadType": "multipart", "supportsAllDrives": "true", "fields": "id"},
            )
            resp.raise_for_status()
        return key

    def load(self, key: str) -> bytes:
        """Driveからバイナリデータを読み込む"""
        file_id = self._find_file(key)
        if not file_id:
            raise FileNotFoundError(f"Key not found: {key}")
        resp = self._session.get(
            f"{self._base_url}/files/{file_id}",
            params={"alt": "media", "supportsAllDrives": "true"},
        )
        resp.raise_for_status()
        return resp.content

    def load_text(self, key: str, encoding: str = "utf-8") -> str:
        return self.load(key).decode(encoding)

    def save_text(self, key: str, text: str, encoding: str = "utf-8") -> str:
        return self.save(key, text.encode(encoding))

    def list_keys(self, prefix: str = "", suffix: str = "") -> list[str]:
        """prefix配下の全ファイルを再帰的にリストアップ"""
        results: list[str] = []
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
            resp = self._files_list(query, "files(id,name,mimeType)", page_token)

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
            self._session.patch(
                f"{self._base_url}/files/{file_id}",
                json={"trashed": True},
                params={"supportsAllDrives": "true"},
            )
