from typing import List, Any, Dict, Optional
from pydantic import BaseModel
import time
import json

class Message(BaseModel):
    """
    A message class for tranferring data between server and client
    """

    sender: str = "System"
    text:   str = ""
    action: str = ""
    created_at:     int = 0
    sender_id:      str = None
    message_id:     Optional[int] = None
    reciepents:     Optional[List[str]] = None
    reciepent_ids:  Optional[List[str]] = None

    @property
    def send_time(self) -> str:
        time_arr = time.localtime(self.created_at)
        time_str = time.strftime("%Y-%m-%d %H:%M:%S", time_arr)
        return time_str

    @staticmethod
    def from_json(msg_bytes):
        msg_dict = json.loads(msg_bytes)
        return Message(**msg_dict)

if __name__ == '__main__':
    msg = Message(text="hello", sender="Bob")
    print(msg)
    print(msg.json())

    msg2 = Message.from_json(msg.json())
    print(msg2)

    msg3 = Message.from_json(msg.json().encode())
    print(msg3)
