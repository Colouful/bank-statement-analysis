# -*- coding: utf-8 -*-
"""数据清洗工具 - 清洗和标准化交易数据"""

import json
import re
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from langchain.tools import tool

from utils.constants import (
    INCOME_EXPENSE_TYPES,
    AMOUNT_PRECISION,
    TIME_FORMATS,
    COMMON_TRANSACTION_TYPES,
    COMMON_TRANSACTION_METHODS
)


def _parse_amount(amount_str: str) -> Tuple[float, Optional[str]]:
    """
    解析金额字符串，返回绝对值和收支类型
    
    Args:
        amount_str: 金额字符串
        
    Returns:
        (绝对值, 收支类型)
    """
    if not amount_str:
        return 0.0, None
    
    # 移除逗号、空格等字符
    amount_str = amount_str.replace(",", "").replace(" ", "").strip()
    
    # 判断收支类型
    income_expense_type = None
    
    # 检查正负号
    if amount_str.startswith("-"):
        income_expense_type = "支出"
        amount_str = amount_str[1:]
    elif amount_str.startswith("+"):
        income_expense_type = "收入"
        amount_str = amount_str[1:]
    
    # 检查中文标识
    if "收入" in amount_str or "存入" in amount_str or "贷" in amount_str:
        income_expense_type = "收入"
    elif "支出" in amount_str or "支取" in amount_str or "借" in amount_str:
        income_expense_type = "支出"
    
    # 提取数字
    amount_match = re.search(r"[-+]?\d+\.?\d*", amount_str)
    if amount_match:
        amount = float(amount_match.group())
        # 如果没有从符号推断出收支类型，从数字正负推断
        if income_expense_type is None:
            if amount < 0:
                income_expense_type = "支出"
                amount = abs(amount)
            elif amount > 0:
                income_expense_type = "收入"
            else:
                income_expense_type = "其他"
        else:
            amount = abs(amount)
        
        # 保留指定精度
        amount = round(amount, AMOUNT_PRECISION)
        return amount, income_expense_type
    
    return 0.0, income_expense_type


def _parse_time(time_str: str) -> Optional[str]:
    """
    解析时间字符串，返回标准化时间格式
    
    Args:
        time_str: 时间字符串
        
    Returns:
        标准化时间字符串
    """
    if not time_str:
        return None
    
    time_str = time_str.strip()
    
    # 尝试各种时间格式
    for fmt in TIME_FORMATS:
        try:
            dt = datetime.strptime(time_str, fmt)
            # 统一输出为 YYYY-MM-DD HH:mm:ss 或 YYYY-MM-DD
            if fmt in ["%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%Y%m%d%H%M%S"]:
                return dt.strftime("%Y-%m-%d %H:%M:%S")
            else:
                return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    
    # 如果都不匹配，尝试正则提取
    # 匹配 YYYY-MM-DD
    date_match = re.search(r"(\d{4})[-/.年](\d{1,2})[-/.月](\d{1,2})", time_str)
    if date_match:
        year, month, day = date_match.groups()
        return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
    
    return time_str  # 返回原始字符串


def _infer_transaction_type(
    transaction_type_col: Optional[str],
    summary_col: Optional[str],
    method_col: Optional[str]
) -> str:
    """
    推断交易类型（优先级 A > B > C）
    
    Args:
        transaction_type_col: 交易类型列的值
        summary_col: 摘要列的值
        method_col: 交易方式列的值
        
    Returns:
        推断出的交易类型
    """
    # 优先级A：从交易类型列提取
    if transaction_type_col:
        for t_type in COMMON_TRANSACTION_TYPES:
            if t_type in str(transaction_type_col):
                return t_type
    
    # 优先级B：从摘要推断
    if summary_col:
        for t_type in COMMON_TRANSACTION_TYPES:
            if t_type in str(summary_col):
                return t_type
    
    # 优先级C：从交易方式推断
    if method_col:
        for t_type in COMMON_TRANSACTION_TYPES:
            if t_type in str(method_col):
                return t_type
    
    # 如果都推断不出，返回"其他"
    return "其他"


def _infer_transaction_method(method_col: Optional[str]) -> str:
    """
    推断交易方式
    
    Args:
        method_col: 交易方式列的值
        
    Returns:
        推断出的交易方式
    """
    if not method_col:
        return ""
    
    method_str = str(method_col)
    
    for method in COMMON_TRANSACTION_METHODS:
        if method in method_str:
            return method
    
    return method_str


@tool
def clean_transaction_data(
    rows: str,
    column_mapping: str,
    org_columns: str
) -> str:
    """
    清洗交易数据
    
    Args:
        rows: JSON字符串格式的数据行
        column_mapping: JSON字符串格式的列名映射关系
        org_columns: JSON字符串格式的原始列名
        
    Returns:
        JSON字符串，包含清洗后的数据
    """
    try:
        # 解析输入
        rows_list = json.loads(rows)
        mapping_dict = json.loads(column_mapping)
        org_columns_list = json.loads(org_columns)
        
        if not isinstance(rows_list, list) or not isinstance(mapping_dict, dict):
            return json.dumps({"error": "输入格式错误"}, ensure_ascii=False)
        
        # 构建列索引映射
        col_index_map = {col: idx for idx, col in enumerate(org_columns_list)}
        
        # 反向映射：标准字段 -> 银行列名列表
        reverse_mapping = {}
        for bank_col, std_field in mapping_dict.items():
            if std_field not in reverse_mapping:
                reverse_mapping[std_field] = []
            reverse_mapping[std_field].append(bank_col)
        
        # 清洗每一行数据
        cleaned_data = []
        
        for row in rows_list:
            cleaned_row = {}
            other_data = {}
            
            # 遍历标准字段
            for std_field in ["交易时间", "收支类型", "金额", "交易对方", 
                            "交易备注/摘要", "交易方式", "交易类型", "余额"]:
                bank_cols = reverse_mapping.get(std_field, [])
                
                # 提取字段值
                field_value = None
                for bank_col in bank_cols:
                    if bank_col in col_index_map:
                        idx = col_index_map[bank_col]
                        if idx < len(row):
                            field_value = row[idx]
                            break
                
                # 根据字段类型进行清洗
                if std_field == "交易时间":
                    cleaned_row[std_field] = _parse_time(field_value) if field_value else ""
                
                elif std_field == "金额":
                    amount, income_expense = _parse_amount(field_value) if field_value else (0.0, None)
                    cleaned_row[std_field] = f"{amount:.{AMOUNT_PRECISION}f}"
                    # 如果收支类型列没有值，从金额推断
                    if income_expense and not cleaned_row.get("收支类型"):
                        cleaned_row["收支类型"] = income_expense
                
                elif std_field == "收支类型":
                    if field_value:
                        field_value_str = str(field_value).strip()
                        for ietype in INCOME_EXPENSE_TYPES:
                            if ietype in field_value_str:
                                cleaned_row[std_field] = ietype
                                break
                        # 如果还没设置，使用默认值
                        if std_field not in cleaned_row:
                            cleaned_row[std_field] = "其他"
                
                elif std_field == "余额":
                    if field_value:
                        amount, _ = _parse_amount(field_value)
                        cleaned_row[std_field] = f"{amount:.{AMOUNT_PRECISION}f}"
                
                else:
                    # 其他字段直接使用原始值
                    cleaned_row[std_field] = field_value if field_value else ""
            
            # 推断交易类型（优先级 A > B > C）
            transaction_type = _infer_transaction_type(
                cleaned_row.get("交易类型"),
                cleaned_row.get("交易备注/摘要"),
                cleaned_row.get("交易方式")
            )
            cleaned_row["交易类型"] = transaction_type
            
            # 推断交易方式
            if cleaned_row.get("交易方式"):
                cleaned_row["交易方式"] = _infer_transaction_method(cleaned_row["交易方式"])
            
            # 收集未映射的字段到"其他"
            for bank_col, std_field in mapping_dict.items():
                if std_field not in ["交易时间", "收支类型", "金额", "交易对方", 
                                   "交易备注/摘要", "交易方式", "交易类型", "余额"]:
                    if bank_col in col_index_map:
                        idx = col_index_map[bank_col]
                        if idx < len(row):
                            other_data[bank_col] = row[idx]
            
            # 如果标准字段中没有匹配到的列，也放入"其他"
            for bank_col in org_columns_list:
                if bank_col not in mapping_dict and bank_col in col_index_map:
                    idx = col_index_map[bank_col]
                    if idx < len(row):
                        other_data[bank_col] = row[idx]
            
            if other_data:
                cleaned_row["其他"] = other_data
            else:
                cleaned_row["其他"] = {}
            
            cleaned_data.append(cleaned_row)
        
        result = {
            "success": True,
            "cleaned_data": cleaned_data,
            "total_rows": len(cleaned_data)
        }
        
        return json.dumps(result, ensure_ascii=False, indent=2)
        
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@tool
def standardize_amount(amount_str: str) -> str:
    """
    标准化金额字符串
    
    Args:
        amount_str: 金额字符串
        
    Returns:
        标准化的金额字符串
    """
    amount, _ = _parse_amount(amount_str)
    return f"{amount:.{AMOUNT_PRECISION}f}"


@tool
def standardize_time(time_str: str) -> str:
    """
    标准化时间字符串
    
    Args:
        time_str: 时间字符串
        
    Returns:
        标准化的时间字符串
    """
    return _parse_time(time_str) or ""
