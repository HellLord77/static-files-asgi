from pydantic_xml import RootXmlModel

from .directory import DirectoryModel
from .file import FileModel


class ListModel(RootXmlModel, tag="list"):
    root: list[DirectoryModel | FileModel]
