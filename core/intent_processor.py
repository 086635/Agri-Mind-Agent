import json
import re

class SmartFarmProcessor:
    """
    智能农场意图处理器
    用于解析AI返回的响应，区分控制指令和问答内容
    """
    
    def __init__(self):
        pass
    
    async def process_ai_response(self, raw_text: str) -> dict:
        """
        处理AI响应
        
        Args:
            raw_text: AI返回的原始文本
            
        Returns:
            包含处理结果的字典
        """
        try:
            original_text = raw_text
            
            json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
            
            if json_match:
                match_start = json_match.start()
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
                
                if json_end > match_start:
                    json_str = raw_text[match_start:json_end]
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
                json_str = json_match.group().strip()
                
                json_str = json_str.replace('\xa0', ' ')
                json_str = ''.join(char for char in json_str if ord(char) >= 32 or char in '\n\r\t')
                json_str = json_str.replace('"', '"').replace('"', '"')
                json_str = re.sub(r'```json[\s\S]*?```', lambda m: m.group().replace('```json', '').replace('```', ''), json_str)
                
                try:
                    data = json.loads(json_str)
                    
                    if "payload" in data:
                        payload = data.get("payload", {})
                        target = payload.get("target", "unknown")
                        cmd = payload.get("cmd", "2")
                        
                        target_map = {
                            "水泵": "pump", "泵": "pump",
                            "风扇": "fan",
                            "灯": "light", "补光灯": "light"
                        }
                        standard_target = target
                        for key, value in target_map.items():
                            if key in target:
                                standard_target = value
                                break
                        
                        device_name = self._device_mapping(standard_target)
                        action = "打开" if str(cmd) == "1" else "关闭"
                        
                        standard_payload = payload.copy()
                        standard_payload["target"] = standard_target
                        
                        cleaned_text = original_text
                        cleaned_text = cleaned_text.replace(json_match.group(), '').strip()
                        cleaned_text = re.sub(r'【控制指令块】|\[控制指令块\]|控制指令块：', '', cleaned_text).strip()
                        cleaned_text = re.sub(r'```[\s\S]*?```', '', cleaned_text).strip()
                        
                        if cleaned_text:
                            response_text = cleaned_text
                        else:
                            response_text = f"收到，正在为您{action}{device_name}"
                        
                        return {
                            "type": "control",
                            "text": response_text,
                            "payload": standard_payload
                        }
                except json.JSONDecodeError as e:
                    print(f"[Intent Processor] JSON解析失败: {e}")
                    return {
                        "type": "qa",
                        "text": original_text,
                        "payload": None
                    }
            
            cleaned_text = re.sub(r'```[\s\S]*?```', '', original_text).strip()
            
            return {
                "type": "qa",
                "text": cleaned_text if cleaned_text else "抱歉，我无法理解您的指令",
                "payload": None
            }
        except Exception as e:
            print(f"[Intent Processor] 处理错误: {e}")
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
