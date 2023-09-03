import logging
import asyncio
import time
import aioconsole

from message import Message
from client import WsClient

def test_one_event_loop():
    user_name = "bob"
    url = "ws://localhost:5555"
    client = WsClient(user_name, url) 

    async def interact(client):
        reader, writer = await aioconsole.get_standard_streams()
        while True:
            text = await reader.readline()
            text = text.decode()
            if not text:
                continue
            msg = Message(
                sender=user_name,
                text=text
            )
            print(f"<< {msg}")
            await client.asend(msg)

    async def output(client):
        while True:
            try:
                msg = await asyncio.wait_for(client.arecv(), timeout=1)
                print(f">> {msg}")
            except asyncio.TimeoutError:
                continue
            except Exception as err:
                logging.exception(err)
                logging.error('connection failed')
                break
    
    task = asyncio.wait([client.repl(), interact(client), output(client)])
    asyncio.get_event_loop().run_until_complete(task)

def test_multi_event_loop():
    user_name = "bob"
    url = "ws://localhost:5555"
    client = WsClient(user_name, url, loop=asyncio.new_event_loop()) 

    cur_loop = asyncio.get_event_loop()
    async def interact(client):
        reader, writer = await aioconsole.get_standard_streams()
        while True:
            text = await reader.readline()
            text = text.decode()
            if not text:
                continue
            msg = Message(
                sender=user_name,
                text=text
            )
            print(f"<< {msg}")
            client.send(msg)

    async def output(client):
        while True:
            try:
                msg = client.recv()
                if not msg:
                    await asyncio.sleep(0.1)
                    continue
                print(f">> {msg}")
            except Exception as err:
                logging.exception(err)
                logging.error('connection failed')
                break
    
    client_loop_process = client.start()
    task = asyncio.wait([output(client), interact(client)])
    cur_loop.run_until_complete(task)
    client_loop_process.join()

def test_sync():
    user_name = "bob"
    url = "ws://localhost:5555"
    client = WsClient(user_name, url, loop=asyncio.new_event_loop()) 
    client.start()
    while True:
        text = input(f"<<")
        msg = Message(
            sender=user_name,
            text=text
        )
        print(f"<< {msg}")
        client.send(msg)

        recv_retry = 50
        for _ in range(recv_retry):
            msg = client.recv()
            if not msg:
                time.sleep(0.1)
                continue
            print(f">> {msg}")

def main():
    import sys
    import inspect
    m = sys.modules[__name__]
    test_funcs = []
    for attr in dir(m):
        if not inspect.isfunction(getattr(m, attr)):
            continue
        if not attr.startswith('test_'):
            continue
        test_funcs.append(attr)
    if len(sys.argv) != 2 or sys.argv[1] not in test_funcs: 
        print(test_funcs)
        return
    getattr(m, sys.argv[1])()

if __name__ == '__main__':
    main()
