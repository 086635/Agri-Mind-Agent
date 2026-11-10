import base64

def image_to_base64(image_path):
    """将裁剪后的图片转为 Base64 字符串"""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')