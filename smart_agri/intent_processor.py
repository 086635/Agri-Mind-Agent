import json
import re

class SmartFarmProcessor:
    """
    智能农场意图处理器
    用于解析AI返回的响应，区分控制指令和问答内容
    """
    
    def __init__(self):
        """
        初始化处理器
        """
        pass
    
    async def process_ai_response(self, raw_text: str) -> dict:
        """
        处理AI响应
        
        Args:
            raw_text: AI返回的原始文本
            
        Returns:
            包含处理结果的字典，格式为：
            {"type": "control" | "qa", "text": "给用户看的文字", "payload": dict | None}
        """
        try:
            # 保存原始文本，用于提取纯文字部分
            original_text = raw_text
            
            # 1. 实现基于正则表达式的 JSON 提取策略
            # 使用正则表达式 r'\{.*\}' (flags=re.DOTALL) 提取AI返回文本中的JSON部分
            json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
            
            # 如果匹配到了，尝试找到完整的JSON结束位置
            if json_match:
                # 提取匹配的部分
                match_start = json_match.start()
                # 从匹配开始位置查找完整的JSON结构
                brace_count = 0
                found_start = False
                json_end = match_start
                
                for i in range(match_start, len(raw_text)):
                    char = raw_text[i]
                    if char == '{':
                        brace_count += 1
                        found_start = True
                    elif char == '}':
                        brace_count -= 1
                        if found_start and brace_count == 0:
                            json_end = i + 1
                            break
                
                # 更新json_match为完整的JSON结构
                if json_end > match_start:
                    json_str = raw_text[match_start:json_end]
                    # 调整匹配对象的位置
                    class Match:
                        def __init__(self, string, start):
                            self.string = string
                            self.start_pos = start
                        def group(self):
                            return self.string
                        def start(self):
                            return self.start_pos
                        def end(self):
                            return self.start_pos + len(self.string)
                    json_match = Match(json_str, match_start)
            
            if json_match:
                # 提取JSON字符串
                json_str = json_match.group().strip()
                
                # 2. 实现 JSON 预处理管道
                # 移除所有 Unicode 不间断空格（\xa0）、制表符及控制字符
                json_str = json_str.replace('\xa0', ' ')
                json_str = ''.join(char for char in json_str if ord(char) >= 32 or char in '\n\r\t')
                
                # 将中文全角引号（" "）强制转换为英文半角引号（"）
                json_str = json_str.replace('“', '"').replace('”', '"')
                
                # 移除 JSON 块外部可能包裹的 ```json 标签
                json_str = re.sub(r'```json[\s\S]*?```', lambda m: m.group().replace('```json', '').replace('```', ''), json_str)
                
                try:
                    # 解析JSON
                    data = json.loads(json_str)
                    
                    # 检查是否为控制指令
                    if "payload" in data:
                        payload = data.get("payload", {})
                        target = payload.get("target", "unknown")
                        cmd = payload.get("cmd", "2")
                        
                        # 确保target是标准英文标识符
                        # 设备名称映射（中文转英文）
                        target_map = {
                            "水泵": "pump", "泵": "pump",
                            "风扇": "fan",
                            "灯": "light", "补光灯": "light"
                        }
                        # 实现模糊匹配映射
                        standard_target = target
                        for key, value in target_map.items():
                            if key in target:
                                standard_target = value
                                break
                        
                        # 构建返回结果
                        device_name = self._device_mapping(standard_target)
                        action = "打开" if str(cmd) == "1" else "关闭"
                        
                        # 返回标准英文target的payload
                        standard_payload = payload.copy()
                        standard_payload["target"] = standard_target
                        
                        # 4. 实现回复文本清洗功能
                        # 从原始回复中剥离 JSON 块及其前缀说明（如“【控制指令块】”）
                        cleaned_text = original_text
                        # 移除JSON块
                        cleaned_text = cleaned_text.replace(json_match.group(), '').strip()
                        # 移除可能的前缀说明
                        cleaned_text = re.sub(r'【控制指令块】|\[控制指令块\]|控制指令块：', '', cleaned_text).strip()
                        # 清洗Markdown标签
                        cleaned_text = re.sub(r'```[\s\S]*?```', '', cleaned_text).strip()
                        
                        # 构建回复文本
                        if cleaned_text:
                            # 如果有剩余的纯文字，使用它作为回复文本
                            response_text = cleaned_text
                        else:
                            # 否则使用默认文本
                            response_text = f"收到，正在为您{action}{device_name}"
                        
                        # 3. 实现统一的输出格式
                        return {
                            "type": "control",
                            "text": response_text,
                            "payload": standard_payload
                        }
                except json.JSONDecodeError as e:
                    # 5. 实现异常处理机制
                    # JSON解析失败，视为问答内容
                    print(f"[Intent Processor] JSON解析失败: {e}")
                    # 即使JSON解析失败，也要返回原始文本
                    # 3. 实现统一的输出格式
                    return {
                        "type": "qa",
                        "text": original_text,
                        "payload": None
                    }
            
            # 非控制指令，视为问答内容
            # 清洗Markdown标签
            cleaned_text = re.sub(r'```[\s\S]*?```', '', original_text).strip()
            
            # 3. 实现统一的输出格式
            return {
                "type": "qa",
                "text": cleaned_text if cleaned_text else "抱歉，我无法理解您的指令",
                "payload": None
            }
        except Exception as e:
            # 5. 实现异常处理机制
            # 异常处理
            print(f"[Intent Processor] 处理错误: {e}")
            # 3. 实现统一的输出格式
            return {
                "type": "qa",
                "text": f"处理指令时出现错误: {str(e)}",
                "payload": None
            }
    
    def _device_mapping(self, target: str) -> str:
        """
        设备名称映射
        
        Args:
            target: 设备英文名称
            
        Returns:
            设备中文名称
        """
        device_map = {
            "pump": "水泵",
            "fan": "风扇",
            "light": "补光灯"
        }
        return device_map.get(target, target)
