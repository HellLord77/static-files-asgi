from pydantic import BaseModel
from starlette.responses import JSONResponse


class PydanticResponse(JSONResponse):
    def render(self, content: BaseModel) -> bytes:
        return content.model_dump_json().encode("utf-8")
