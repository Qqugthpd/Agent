import json
import hashlib
from datetime import datetime

class TraceLogger:
    def __init__(self, output_path="trace.jsonl"):
        self.output_path = output_path

    def log_file_access(self, file_path):
        """记录文件访问，附带SHA256哈希，证明文件未被篡改"""
        with open(file_path, "rb") as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()[:16]
        
        entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "file_access",
            "file": file_path,
            "file_hash": file_hash
        }
        self._write(entry)

    def log_tool_call(self, step, tool_name, arguments, result):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "tool_call",
            "step": step,
            "tool": tool_name,
            "arguments": arguments,
            "result": result
        }
        self._write(entry)

    def _write(self, entry):
        with open(self.output_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")