from fastapi import Response
from pydantic_xml import BaseXmlModel


class PydanticXMLResponse(Response):
    media_type = "application/xml"

    def render(self, content: BaseXmlModel) -> bytes:
        return content.to_xml(exclude_unset=True)
