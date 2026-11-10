from flask import Flask, jsonify, redirect
import requests

# 创建Flask应用实例
app = Flask(__name__)

# 根路径 - 重定向到 /monitor
@app.route("/")
def root():
    return redirect("/monitor")

# 健康检查端点
@app.route("/health")
def health_check():
    return jsonify({"status": "healthy"})

# 监控路径 - 转发到 STM32 模拟器的监控端点
@app.route("/monitor")
def monitor():
    try:
        # 尝试连接到STM32模拟器
        response = requests.get("http://localhost:8000/monitor", timeout=1.0)
        
        # 检查响应状态码
        if response.status_code == 200:
            # 直接返回响应内容
            return response.content, response.status_code, response.headers.items()
        else:
            return jsonify({"status": "error", "message": f"Failed to fetch monitor data: {response.status_code}"}), response.status_code
    except requests.exceptions.ConnectionError:
        # 当STM32模拟器未启动时的错误处理
        return jsonify({"status": "error", "message": "STM32 simulator is not running. Please start the simulator first."}), 503
    except requests.exceptions.RequestException as e:
        # 其他请求错误处理
        return jsonify({"status": "error", "message": f"Failed to connect to STM32 simulator: {str(e)}"}), 503
    except Exception as e:
        # 其他错误处理
        return jsonify({"status": "error", "message": f"Internal server error: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=9003,
        debug=True
    )