from datetime import datetime
from typing import Literal

from pydantic_xml import attr

from .base import ModelBase


class FileModel(ModelBase, tag="file"):
    name: str
    type: Literal["file"] = "file"
    mtime: datetime = attr()
    size: int = attr()
