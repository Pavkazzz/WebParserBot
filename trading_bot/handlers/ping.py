import fast_json
from aiohttp.web_response import json_response
from aiohttp.web_urldispatcher import View


class PingHandler(View):
    async def get(self):
        return json_response(data={"status": "ok"}, dumps=fast_json.dumps)
