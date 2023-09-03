from typing import List, Union
import time

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, Query, Cookie
from fastapi.responses import HTMLResponse
from message import Message

app = FastAPI()

html = """
<!DOCTYPE html>
<html>
    <head>
        <title>Chat</title>
    </head>
    <body>
        <h1>WebSocket Chat</h1>
            <label>UserName: <input type="text" id="user_name" autocomplete="off" value="SomeOne"/></label>
            <label>Token: <input type="text" id="token" autocomplete="off" value="some-key-token"/></label>
            <button onclick="connect(event)">Connect</button>
        <form action="" onsubmit="sendMessage(event)">
            <hr>
            <label>Message: <input type="text" id="messageText" autocomplete="off"/></label>
            <button>Send</button>
        </form>
        <ul id='messages'>
        </ul>
        <script>
            var ws = null;
            var user_name = null;
            var token = null;
            function connect(event) {
                user_name = document.getElementById("user_name").value
                token = document.getElementById("token").value
                var client_id = user_name
                var ws_url = "ws://" + window.location.host + "/ws/" + client_id + "?token=" + token
                ws = new WebSocket(ws_url)
                ws.onmessage = function(event) {
                    var messages = document.getElementById('messages')
                    var message = document.createElement('li')
                    var msg = JSON.parse(event.data)
                    var content = document.createTextNode(msg.sender + ": " + msg.text)
                    message.appendChild(content)
                    messages.appendChild(message)
                };
                event.preventDefault()
            }

            function sendMessage(event) {
                var input = document.getElementById("messageText")
                msg = {
                    "sender": user_name,
                    "text": input.value,
                }

                var messages = document.getElementById('messages')
                var message = document.createElement('li')
                var content = document.createTextNode(msg.sender + ": " + msg.text)
                message.appendChild(content)
                messages.appendChild(message)
                ws.send(JSON.stringify(msg))
                input.value = ''
                event.preventDefault()
            }
        </script>
    </body>
</html>
"""


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: Message, websocket: WebSocket):
        await websocket.send_text(message.json())

    async def broadcast(self, message: Message):
        for connection in self.active_connections:
            await connection.send_text(message.json())


manager = ConnectionManager()


@app.get("/")
async def get():
    return HTMLResponse(html)

async def get_cookie_or_token(
        websocket: WebSocket,
        sid: Union[str, None] = Cookie(default=None),
        token: Union[str, None] = Query(default=None),
):
    # validate it
#    if sid is None and token is None:
#        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
    return sid, token

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str,
        sid_or_token: str = Depends(get_cookie_or_token)):
    await manager.connect(websocket)
    sid, token = sid_or_token
    token = token or sid
    print(f'token:{token}')
    try:
        while True:
            data = await websocket.receive_text()
            msg = Message.from_json(data)
            await manager.broadcast(Message(text=f'#{client_id}:' + msg.text, created_at=int(time.time())))
            msg.sender = "Bot"
            msg.text = 'reply: ' + msg.text
            msg.created_at = int(time.time())
            await manager.send_personal_message(msg, websocket)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        msg = Message(text=f'#{client_id} left the chat', created_at=int(time.time()))
        await manager.broadcast(msg)

