"""
ストレージ抽象層
全ファイルI/OはこのBackend経由で行い、ローカルパスに直接依存しない。
将来GCS/S3等に差し替え可能。
"""

from __future__ import annotations

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
