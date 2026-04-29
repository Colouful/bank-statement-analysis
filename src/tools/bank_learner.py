"""
银行映射规则自动学习工具
当识别到新的银行流水时，自动保存映射关系到规则文件
"""

import json
import os
from datetime import datetime
from typing import Dict, List
from langchain.tools import tool
from coze_coding_utils.log.write_log import request_context
from coze_coding_utils.runtime_ctx.context import new_context


@tool
def save_bank_mapping(
    bank_name: str,
    original_columns: List[str],
    mapping: Dict[str, str],
    confidence: float = 0.95
) -> str:
    """
    保存新银行的列名映射关系到规则文件
    
    参数:
        bank_name: 银行名称（如：工商银行、农业银行等）
        original_columns: 原始列名列表
        mapping: 列名映射关系 {原始列名: 标准字段}
        confidence: 映射置信度（0-1），默认0.95
    
    返回:
        JSON格式的保存结果
    """
    ctx = request_context.get() or new_context(method="save_bank_mapping")
    
    workspace_path = os.getenv("COZE_WORKSPACE_PATH", "/workspace/projects")
    mapping_file = os.path.join(workspace_path, "assets/bank_columns.json")
    
    try:
        # 读取现有的映射规则
        with open(mapping_file, 'r', encoding='utf-8') as f:
            mapping_data = json.load(f)
        
        # 标准字段列表
        standard_fields = [
            "交易时间", "收支类型", "金额", "交易对方", "交易备注/摘要",
            "交易方式", "交易类型", "余额", "其他"
        ]
        
        # 遍历映射关系，保存到对应的标准字段
        new_mappings = {}
        updated_fields = []
        
        for original_col, standard_field in mapping.items():
            if standard_field in standard_fields:
                # 检查该列名是否已经存在
                if original_col not in mapping_data.get(standard_field, []):
                    if standard_field not in mapping_data:
                        mapping_data[standard_field] = []
                    mapping_data[standard_field].append(original_col)
                    new_mappings[original_col] = standard_field
                    updated_fields.append(standard_field)
        
        # 如果有新的映射关系，保存元数据
        if new_mappings:
            # 添加学习记录
            if "_learning_history" not in mapping_data:
                mapping_data["_learning_history"] = []
            
            learning_record = {
                "bank_name": bank_name,
                "timestamp": datetime.now().isoformat(),
                "new_mappings": new_mappings,
                "confidence": confidence,
                "total_columns": len(original_columns)
            }
            mapping_data["_learning_history"].append(learning_record)
            
            # 只保留最近100条学习记录
            if len(mapping_data["_learning_history"]) > 100:
                mapping_data["_learning_history"] = mapping_data["_learning_history"][-100:]
        
        # 保存到文件
        with open(mapping_file, 'w', encoding='utf-8') as f:
            json.dump(mapping_data, f, ensure_ascii=False, indent=2)
        
        result = {
            "success": True,
            "bank_name": bank_name,
            "new_mappings_saved": len(new_mappings),
            "updated_fields": list(set(updated_fields)),
            "mapping_details": new_mappings,
            "confidence": confidence,
            "message": f"成功保存 {len(new_mappings)} 个新的映射关系到规则文件"
        }
        
        return json.dumps(result, ensure_ascii=False, indent=2)
        
    except FileNotFoundError:
        error_result = {
            "success": False,
            "error": "映射规则文件不存在",
            "message": "无法找到 bank_columns.json 文件",
            "file_path": mapping_file
        }
        return json.dumps(error_result, ensure_ascii=False)
        
    except json.JSONDecodeError as e:
        error_result = {
            "success": False,
            "error": "映射规则文件格式错误",
            "message": f"JSON解析失败: {str(e)}",
            "file_path": mapping_file
        }
        return json.dumps(error_result, ensure_ascii=False)
        
    except Exception as e:
        error_result = {
            "success": False,
            "error": "保存映射关系失败",
            "message": str(e),
            "file_path": mapping_file,
            "error_type": type(e).__name__
        }
        return json.dumps(error_result, ensure_ascii=False)


@tool
def get_learning_history(limit: int = 10) -> str:
    """
    获取银行映射规则的学习历史
    
    参数:
        limit: 返回的记录数量，默认10条
    
    返回:
        JSON格式的学习历史记录
    """
    ctx = request_context.get() or new_context(method="get_learning_history")
    
    workspace_path = os.getenv("COZE_WORKSPACE_PATH", "/workspace/projects")
    mapping_file = os.path.join(workspace_path, "assets/bank_columns.json")
    
    try:
        with open(mapping_file, 'r', encoding='utf-8') as f:
            mapping_data = json.load(f)
        
        history = mapping_data.get("_learning_history", [])
        
        # 返回最近的N条记录
        recent_history = history[-limit:] if len(history) > limit else history
        
        # 反转顺序，最新的在前面
        recent_history = list(reversed(recent_history))
        
        result = {
            "success": True,
            "total_records": len(history),
            "returned_records": len(recent_history),
            "history": recent_history
        }
        
        return json.dumps(result, ensure_ascii=False, indent=2)
        
    except FileNotFoundError:
        return json.dumps({
            "success": False,
            "error": "映射规则文件不存在",
            "message": "还没有学习记录"
        }, ensure_ascii=False)
        
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e),
            "message": "获取学习历史失败"
        }, ensure_ascii=False)
