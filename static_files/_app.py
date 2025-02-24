from asyncio import Lock
from datetime import UTC
from datetime import datetime
from http import HTTPStatus
from os import stat_result
from pathlib import Path
from stat import S_ISDIR
from stat import S_ISLNK
from typing import override
from weakref import WeakValueDictionary

from anyio.to_thread import run_sync
from starlette._utils import get_route_path
from starlette.datastructures import URL
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import RedirectResponse
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

from .enums import FormatEnum
from .models import DirectoryModel
from .models import FileModel
from .models import ListModel
from .responses import PydanticResponse
from .responses import PydanticXMLResponse
from .responses import TemplateResponse


class _StaticFiles(StaticFiles):
    @override
    def __init__(
        self,
        *args,  # noqa: ANN002
        dotfiles: bool = False,
        autoindex: bool = False,
        autoindex_exact_size: bool = True,
        autoindex_localtime: bool = False,
        autoindex_format: FormatEnum = FormatEnum.HTML,
        **kwargs,  # noqa: ANN003
    ) -> None:
        super().__init__(*args, **kwargs)
        self._lookup_path_lock_map_lock = Lock()
        self._lookup_path_lock_map = WeakValueDictionary()
        self._lookup_path_cache = {}

        self.dotfiles = dotfiles
        self.autoindex = autoindex
        self.autoindex_exact_size = autoindex_exact_size
        self.autoindex_format = autoindex_format
        self.autoindex_localtime = autoindex_localtime

    @override
    def get_path(self, scope: Scope) -> str:
        path = super().get_path(scope)

        if not self.dotfiles:
            for part in Path(path).parts:
                if part.startswith("."):
                    raise HTTPException(HTTPStatus.NOT_FOUND)

        return path

    @override
    async def get_response(self, path: str, scope: Scope) -> Response:
        async with self._lookup_path_lock_map_lock:
            try:
                lock = self._lookup_path_lock_map[path]
            except KeyError:
                lock = self._lookup_path_lock_map[path] = Lock()

        http_exception = None
        async with lock:
            try:
                return await super().get_response(path, scope)
            except HTTPException as exception:
                http_exception = exception
            finally:
                full_path, stat = self._lookup_path_cache.pop(path, ("", None))

        if stat is None or http_exception.status_code != HTTPStatus.NOT_FOUND:
            raise http_exception

        if self.autoindex and S_ISDIR(stat.st_mode):
            if not scope["path"].endswith("/"):
                url = URL(scope=scope)
                return RedirectResponse(url.replace(path=url.path + "/"))
            return await run_sync(self.autoindex_response, Path(full_path), scope)

        raise http_exception

    @override
    def lookup_path(self, path: str) -> tuple[str, stat_result | None]:
        lookup_path_result = super().lookup_path(path)
        self._lookup_path_cache[path] = lookup_path_result
        return lookup_path_result

    def autoindex_response(self, path: Path, scope: Scope) -> Response:
        directories = []
        files = []
        for child_path in path.iterdir():
            if not self.dotfiles and child_path.name.startswith("."):
                continue

            stat = child_path.stat()
            if not self.follow_symlink and S_ISLNK(stat.st_mode):
                continue

            mtime = datetime.fromtimestamp(
                stat.st_mtime, None if self.autoindex_localtime and self.autoindex_format == FormatEnum.HTML else UTC
            )
            if S_ISDIR(stat.st_mode):
                directories.append(DirectoryModel(name=child_path.name, mtime=mtime))
            else:
                files.append(FileModel(name=child_path.name, size=stat.st_size, mtime=mtime))

        if self.autoindex_format == FormatEnum.HTML:
            return TemplateResponse(
                Request(scope),
                "autoindex.html.jinja2",
                {
                    "route_path": get_route_path(scope),
                    "exact_size": self.autoindex_exact_size,
                    "dirs": directories,
                    "files": files,
                },
            )

        list_ = ListModel(root=directories + files)
        match self.autoindex_format:
            case FormatEnum.XML:
                return PydanticXMLResponse(list_)
            case FormatEnum.JSON:
                return PydanticResponse(list_)
            case _:
                raise NotImplementedError
