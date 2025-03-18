from collections.abc import Awaitable
from collections.abc import Callable
from datetime import UTC
from datetime import datetime
from errno import ENAMETOOLONG
from http import HTTPStatus
from pathlib import Path
from stat import S_ISDIR
from stat import S_ISLNK
from typing import override

from aiopath import AsyncPath
from anyio.to_thread import run_sync
from starlette._utils import get_route_path
from starlette.datastructures import URL
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import RedirectResponse
from starlette.responses import Response
from starlette.staticfiles import PathLike
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
        not_found_handler: Callable[[PathLike, Scope], Awaitable[Response]] | None = None,
        not_found_handler_dir: Callable[[PathLike, Scope], Awaitable[Response]] | None = None,
        **kwargs,  # noqa: ANN003
    ) -> None:
        super().__init__(*args, **kwargs)

        self.dotfiles = dotfiles

        self.autoindex = autoindex
        self.autoindex_exact_size = autoindex_exact_size
        self.autoindex_format = autoindex_format
        self.autoindex_localtime = autoindex_localtime

        self.not_found_handler = not_found_handler
        self.not_found_handler_dir = not_found_handler_dir

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
        try:
            return await super().get_response(path, scope)
        except HTTPException as exception:
            if exception.status_code == HTTPStatus.NOT_FOUND:
                try:
                    full_path, stat = await run_sync(self.lookup_path, path)
                except OSError as exception:
                    if exception.errno == ENAMETOOLONG:
                        raise HTTPException(HTTPStatus.NOT_FOUND) from exception
                    raise

                if stat is None:
                    if self.not_found_handler is not None:
                        return await self.not_found_handler(path, scope)

                elif self.not_found_handler_dir is not None and S_ISDIR(stat.st_mode):
                    return await self.not_found_handler_dir(path, scope)

                elif self.autoindex and S_ISDIR(stat.st_mode):
                    if not scope["path"].endswith("/"):
                        url = URL(scope=scope)
                        return RedirectResponse(url.replace(path=url.path + "/"))
                    return await self.autoindex_response(full_path, scope)
            raise

    async def autoindex_response(self, full_path: PathLike, scope: Scope) -> Response:
        directories = []
        files = []
        async for child_path in AsyncPath(full_path).iterdir():
            if not self.dotfiles and child_path.name.startswith("."):
                continue

            stat = await child_path.stat(follow_symlinks=self.follow_symlink)
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
