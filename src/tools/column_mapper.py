# -*- coding: utf-8 -*-
"""列名映射工具 - 将银行列名映射到标准字段"""

import json
import os
from typing import Dict, List, Any, Optional
from langchain.tools import tool
from coze_coding_dev_sdk import LLMClient
from coze_coding_utils.runtime_ctx.context import new_context
from langchain_core.messages import SystemMessage, HumanMessage

from utils.constants import (
    BANK_COLUMNS_MAPPING,
    STANDARD_FIELDS,
    REQUIRED_FIELDS,
    BANK_KEYWORDS
)


def _load_bank_columns_mapping() -> Dict[str, Any]:
    """加载银行列名映射表"""
    try:
        with open(BANK_COLUMNS_MAPPING, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"加载银行列名映射表失败: {e}")
        return {}


def _exact_match_column(column_name: str, mapping_data: Dict[str, Any]) -> Optional[str]:
    """
    精确匹配列名
    
    Args:
        column_name: 银行列名
        mapping_data: 映射数据
        
    Returns:
        匹配到的标准字段，None表示未匹配
    """
    column_name = column_name.strip()
    
    # 遍历标准字段
    for std_field, field_info in mapping_data.get("standard_fields", {}).items():
        synonyms = field_info.get("synonyms", [])
        
        # 精确匹配
        if column_name in synonyms:
            return std_field
        
        # 忽略大小写和空格匹配
        if column_name.lower().replace(" ", "") in [s.lower().replace(" ", "") for s in synonyms]:
            return std_field
    
    return None


def _llm_semantic_match(columns: List[str], unmatched: List[str]) -> Dict[str, str]:
    """
    使用LLM进行语义匹配
    
    Args:
        columns: 所有列名
        unmatched: 未匹配的列名
        
    Returns:
        映射关系字典
    """
    if not unmatched:
        return {}
    
    mapping_data = _load_bank_columns_mapping()
    
    # 构建标准字段描述
    std_fields_desc = []
    for std_field in STANDARD_FIELDS:
        field_info = mapping_data.get("standard_fields", {}).get(std_field, {})
        std_fields_desc.append(
            f"- {std_field}: {field_info.get('description', '')} "
            f"(同义词: {', '.join(field_info.get('synonyms', [])[:5])})"
        )
    
    # 构建提示词
    system_prompt = """你是银行流水解析专家，擅长理解银行列名的语义含义。

你的任务是将银行列名映射到标准字段。请根据列名的语义含义，选择最合适的标准字段。

标准字段定义：
{}

映射规则：
1. 优先语义匹配，而不是字面匹配
2. 考虑列名的实际含义（比如"借方"对应"支出"，"贷方"对应"收入"）
3. 如果无法匹配，返回None

输出格式（只返回JSON，不要其他说明）：
{{
  "银行列名": "标准字段名",
  ...
}}
""".format("\n".join(std_fields_desc))
    
    human_message = f"""请将以下银行列名映射到标准字段：

银行列名列表：
{', '.join(unmatched)}

标准字段列表：
{', '.join(STANDARD_FIELDS)}

请返回映射关系（JSON格式）。"""

    try:
        ctx = new_context(method="column_mapping")
        client = LLMClient(ctx=ctx)
        
        response = client.invoke(
            messages=[
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_message)
            ],
            model="doubao-seed-2-0-pro-260215",
            temperature=0.3,
            max_completion_tokens=4096
        )
        
        # 解析响应
        content = response.content
        if isinstance(content, str):
            content = content.strip()
        
        # 尝试提取JSON
        if isinstance(content, str):
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
        
        return json.loads(content)
        
    except Exception as e:
        print(f"LLM语义匹配失败: {e}")
        return {}


@tool
def map_columns(headers: str) -> str:
    """
    将银行列名映射到标准字段
    
    Args:
        headers: JSON字符串格式的列名列表
        
    Returns:
        JSON字符串，包含映射关系
    """
    try:
        # 解析输入
        headers_list = json.loads(headers)
        
        if not isinstance(headers_list, list):
            return json.dumps({"error": "headers必须是列表格式"}, ensure_ascii=False)
        
        # 加载映射数据
        mapping_data = _load_bank_columns_mapping()
        
        # 第一步：精确匹配
        column_mapping = {}
        matched = set()
        unmatched = []
        
        for column in headers_list:
            std_field = _exact_match_column(column, mapping_data)
            if std_field:
                column_mapping[column] = std_field
                matched.add(column)
            else:
                unmatched.append(column)
        
        # 第二步：LLM语义匹配（仅针对未匹配的列）
        if unmatched:
            llm_mapping = _llm_semantic_match(headers_list, unmatched)
            for column, std_field in llm_mapping.items():
                if std_field and std_field in STANDARD_FIELDS:
                    column_mapping[column] = std_field
                    matched.add(column)
        
        # 第三步：未匹配的列放入"其他"
        other_columns = [col for col in headers_list if col not in matched]
        
        result = {
            "mapping": column_mapping,
            "unmapped_columns": other_columns,
            "all_columns": headers_list,
            "standard_fields": STANDARD_FIELDS,
            "mapped_count": len(column_mapping),
            "unmapped_count": len(other_columns)
        }
        
        return json.dumps(result, ensure_ascii=False, indent=2)
        
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@tool
def detect_bank_from_columns(headers: str) -> str:
    """
    根据列名识别银行
    
    Args:
        headers: JSON字符串格式的列名列表
        
    Returns:
        JSON字符串，包含识别结果
    """
    try:
        headers_list = json.loads(headers)
        headers_text = " ".join(headers_list)
        
        mapping_data = _load_bank_columns_mapping()
        bank_specific = mapping_data.get("bank_specific_fields", {})
        
        detected_banks = []
        
        for bank_name, fields in bank_specific.items():
            bank_keywords = list(fields.keys()) + BANK_KEYWORDS.get(bank_name, [])
            match_count = sum(1 for keyword in bank_keywords if keyword in headers_text)
            if match_count > 0:
                detected_banks.append({
                    "bank": bank_name,
                    "match_count": match_count,
                    "matched_fields": [f for f in bank_keywords if f in headers_text]
                })
        
        # 按匹配数量排序
        detected_banks.sort(key=lambda x: x["match_count"], reverse=True)
        
        result = {
            "detected_banks": detected_banks,
            "primary_bank": detected_banks[0]["bank"] if detected_banks else None,
            "confidence": detected_banks[0]["match_count"] if detected_banks else 0
        }
        
        return json.dumps(result, ensure_ascii=False, indent=2)
        
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# 辅助函数：反向映射（标准字段 -> 银行列名）
def get_reverse_mapping(column_mapping: Dict[str, str]) -> Dict[str, List[str]]:
    """
    获取反向映射关系
    
    Args:
        column_mapping: 正向映射（银行列名 -> 标准字段）
        
    Returns:
        反向映射（标准字段 -> 银行列名列表）
    """
    reverse_mapping = {std_field: [] for std_field in STANDARD_FIELDS}
    
    for bank_col, std_field in column_mapping.items():
        if std_field in reverse_mapping:
            reverse_mapping[std_field].append(bank_col)
    
    return reverse_mapping
