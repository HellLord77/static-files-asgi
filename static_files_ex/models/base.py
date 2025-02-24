from datetime import datetime

from pydantic import ConfigDict
from pydantic_xml import BaseXmlModel
from pydantic_xml import xml_field_serializer
from pydantic_xml.element import XmlElementWriter


class ModelBase(BaseXmlModel):
    @xml_field_serializer("mtime")
    def mtime_serializer(self, element: XmlElementWriter, value: datetime, field_name: str) -> None:
        element.set_attribute(field_name, value.strftime("%Y-%m-%dT%H:%M:%SZ"))

    model_config = ConfigDict(json_encoders={datetime: lambda value: value.strftime("%a, %d %b %Y %H:%M:%S GMT")})
