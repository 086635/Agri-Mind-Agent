import socket
import threading

# 处理客户端请求
def handle_client(client_socket):
    try:
        # 接收客户端请求
        request = client_socket.recv(1024).decode('utf-8')
        print(f"Received request: {request}")
        
        # 解析请求路径
        path = request.split(' ')[1]
        
        if path == '/monitor':
            # 返回STM32模拟器未启动的错误信息
            response = b"HTTP/1.1 503 Service Unavailable\r\n"
            response += b"Content-Type: application/json\r\n"
            response += b"\r\n"
            response += b'{"status": "error", "message": "STM32 simulator is not running. Please start the simulator first."}'
        elif path == '/health':
            # 返回健康检查信息
            response = b"HTTP/1.1 200 OK\r\n"
            response += b"Content-Type: application/json\r\n"
            response += b"\r\n"
            response += b'{"status": "healthy"}'
        else:
            # 重定向到 /monitor
            response = b"HTTP/1.1 302 Found\r\n"
            response += b"Location: /monitor\r\n"
            response += b"\r\n"
        
        # 发送响应
        client_socket.sendall(response)
    except Exception as e:
        print(f"Error handling client: {e}")
    finally:
        # 关闭客户端连接
        client_socket.close()

# 启动服务器
def start_server():
    # 创建socket
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    # 绑定地址和端口
    server_socket.bind(('0.0.0.0', 9009))
    
    # 开始监听
    server_socket.listen(5)
    print("Socket server running at http://0.0.0.0:9009")
    
    while True:
        # 接受客户端连接
        client_socket, client_address = server_socket.accept()
        print(f"Accepted connection from {client_address}")
        
        # 创建线程处理客户端请求
        client_thread = threading.Thread(target=handle_client, args=(client_socket,))
        client_thread.daemon = True
        client_thread.start()

if __name__ == "__main__":
    start_server()