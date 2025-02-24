from datetime import datetime
from typing import Literal

from pydantic_xml import attr

from .base import ModelBase


class DirectoryModel(ModelBase, tag="directory"):
    name: str
    type: Literal["directory"] = "directory"
    mtime: datetime = attr()
