import http.server
import socketserver

# 定义HTTP请求处理器
class MyHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/monitor':
            # 返回STM32模拟器未启动的错误信息
            self.send_response(503)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"status": "error", "message": "STM32 simulator is not running. Please start the simulator first."}')
        elif self.path == '/health':
            # 返回健康检查信息
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"status": "healthy"}')
        else:
            # 重定向到 /monitor
            self.send_response(302)
            self.send_header('Location', '/monitor')
            self.end_headers()

# 启动HTTP服务器
PORT = 9007
Handler = MyHandler
with socketserver.TCPServer(("127.0.0.1", PORT), Handler) as httpd:
    print(f"Server running at http://127.0.0.1:{PORT}")
    httpd.serve_forever()