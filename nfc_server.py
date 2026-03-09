import asyncio
import websockets
import json
from smartcard.System import readers
from smartcard.util import toHexString
from smartcard.CardMonitoring import CardMonitor, CardObserver

# --- 配置 ---
PORT = 8765
connected_clients = set()

# --- 读卡器逻辑 ---
class PrintObserver(CardObserver):
    """监听卡片插入和移除"""
    def update(self, observable, actions):
        (addedcards, removedcards) = actions
        for card in addedcards:
            try:
                card.connection = card.createConnection()
                card.connection.connect()
                # 发送获取 UID 的 APDU 指令
                get_uid = [0xFF, 0xCA, 0x00, 0x00, 0x00]
                response, sw1, sw2 = card.connection.transmit(get_uid)
                
                # 将 UID 转换为字符串
                uid_str = toHexString(response).replace(" ", "")
                print(f"[NFC] 检测到卡片: {uid_str}")
                
                # 发送给网页
                asyncio.run_coroutine_threadsafe(broadcast_uid(uid_str), loop)
            except Exception as e:
                print(f"读卡错误: {e}")

async def broadcast_uid(uid):
    """将 UID 发送给所有连接的网页"""
    if connected_clients:
        message = json.dumps({"type": "card_tap", "uid": uid})
        await asyncio.gather(*(client.send(message) for client in connected_clients))

# --- WebSocket 服务器逻辑 ---
async def handler(websocket):
    print("[WS] 网页已连接")
    connected_clients.add(websocket)
    try:
        await websocket.wait_closed()
    finally:
        connected_clients.remove(websocket)
        print("[WS] 网页断开连接")

async def main():
    print(">>> 正在寻找 ACR122U 读卡器...")
    try:
        available_readers = readers()
    except Exception as e:
        print(f"!!! 驱动错误: {e}")
        return

    if not available_readers:
        print("!!! 未找到读卡器，请检查 USB 连接 !!!")
        print("如果是 macOS，请确保读卡器已插入且驱动已安装。")
    else:
        print(f">>> 已连接读卡器: {available_readers[0]}")
        monitor = CardMonitor()
        observer = PrintObserver()
        monitor.addObserver(observer)

    print(f">>> 服务已启动，请打开网页。监听端口: {PORT}")
    async with websockets.serve(handler, "localhost", PORT):
        await asyncio.get_running_loop().create_future()

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("程序已停止")