"""Тестовый WebSocket-сервер под протокол мессенджера.
   Слушает 0.0.0.0:8080, значит доступен по локальной сети.
"""

import asyncio
import json
import logging

import websockets

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
log = logging.getLogger("server")

HOST = "192.168.0.100"       # ← важно: слушаем все интерфейсы
PORT = 8080

HOST=192.168.0.100
PORT= 8080
WS_URL=ws://HOST:PORT/chat

clients: dict = {}
next_id = 1


async def handler(ws):
    global next_id
    try:
        await ws.send("CONNECTED")

        async for raw in ws:
            log.info("← %s", raw)
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send(json.dumps({
                    "respType": "error",
                    "errorText": "bad json",
                }))
                continue

            req = data.get("reqType", "")

            # -------- регистрация имени --------
            if req == "setMyName":
                name = data.get("newName", "?")
                my_id = next_id
                next_id += 1
                clients[ws] = {"id": my_id, "name": name}

                await ws.send(json.dumps({
                    "respType": "success",
                    "successText": f"User with ID {my_id} has name {name}",
                }))
                log.info("Зарегистрирован %s (id=%s)", name, my_id)

            # -------- общий чат --------
            elif req == "reqSendAll":
                text = data.get("message", "")
                sender = clients.get(ws, {"id": 0, "name": "?"})
                payload = json.dumps({
                    "respType": "sendMessage",
                    "fromUser": sender,
                    "message": text,
                })
                delivered = 0
                for client in list(clients):
                    try:
                        await client.send(payload)
                        delivered += 1
                    except Exception:
                        clients.pop(client, None)

                await ws.send(json.dumps({
                    "respType": "success",
                    "successText": f"Message was delivered to users: {delivered}",
                }))

            # -------- личное --------
            elif req == "reqSendMessage":
                text = data.get("message", "")
                to_user = data.get("userTo") or {}  # ← userTo
                target_id = to_user.get("id")
                target_name = to_user.get("name")
                sender = clients.get(ws, {"id": 0, "name": "?"})

                delivered = False
                for client, info in list(clients.items()):
                    match = False
                    if target_id and info.get("id") == target_id:
                        match = True
                    elif target_name and info.get("name") == target_name:
                        match = True

                    if match:
                        try:
                            await client.send(json.dumps({
                                "respType": "sendMessage",
                                "fromUser": sender,
                                "toUser": info,
                                "message": text,
                            }))
                            delivered = True
                        except Exception:
                            clients.pop(client, None)
                        break

                await ws.send(json.dumps({
                    "respType": "success",
                    "successText": f"Private message delivered: {delivered}",
                }))
                delivered = False
                for client, info in list(clients.items()):
                    if info.get("id") == target_id:
                        try:
                            await client.send(json.dumps({
                                "respType": "sendMessage",
                                "fromUser": sender,
                                "toUser": info,
                                "message": text,
                            }))
                            delivered = True
                        except Exception:
                            clients.pop(client, None)
                        break

                await ws.send(json.dumps({
                    "respType": "success",
                    "successText": f"Private message delivered: {delivered}",
                }))

            else:
                await ws.send(json.dumps({
                    "respType": "error",
                    "errorText": f"unknown reqType: {req}",
                }))

    finally:
        clients.pop(ws, None)
        log.info("Клиент отключился")


async def main():
    async with websockets.serve(handler, HOST, PORT):
        log.info("Сервер запущен: ws://%s:%s/chat", HOST, PORT)
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())