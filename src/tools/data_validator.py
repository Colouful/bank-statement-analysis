# -*- coding: utf-8 -*-
"""数据验证工具 - 多轮验证确保数据准确性"""

import json
from typing import Dict, List, Any, Optional
from decimal import Decimal, getcontext
from langchain.tools import tool

# 设置高精度计算
getcontext().prec = 20

from utils.constants import REQUIRED_FIELDS, AMOUNT_PRECISION


@tool
def validate_transaction_data(transactions: str) -> str:
    """
    多轮验证交易数据
    
    Args:
        transactions: JSON字符串格式的交易数据数组
        
    Returns:
        JSON字符串，包含验证结果
    """
    try:
        transactions_list = json.loads(transactions)
        
        if not isinstance(transactions_list, list):
            return json.dumps({"error": "输入格式错误，需要数组"}, ensure_ascii=False)
        
        if len(transactions_list) == 0:
            return json.dumps({"error": "没有交易数据"}, ensure_ascii=False)
        
        validation_results = {
            "success": True,
            "total_rows": len(transactions_list),
            "valid_rows": 0,
            "errors": [],
            "warnings": [],
            "checks": {
                "required_fields": True,
                "balance_continuity": True,
                "amount_balance": True,
                "time_order": True
            }
        }
        
        # 验证1：必填字段检查
        required_field_errors = []
        for idx, tx in enumerate(transactions_list):
            for field in REQUIRED_FIELDS:
                if field not in tx or not tx[field] or str(tx[field]).strip() == "":
                    required_field_errors.append({
                        "row_index": idx,
                        "field": field,
                        "error": f"缺少必填字段或字段为空: {field}"
                    })
        
        if required_field_errors:
            validation_results["checks"]["required_fields"] = False
            validation_results["errors"].extend(required_field_errors)
        
        # 验证2：余额连续性检查
        balance_errors = []
        prev_balance = None
        
        for idx, tx in enumerate(transactions_list):
            balance_str = tx.get("余额", "0")
            if not balance_str or str(balance_str).strip() == "":
                balance_errors.append({
                    "row_index": idx,
                    "error": "余额字段为空"
                })
                continue
            
            try:
                balance = Decimal(str(balance_str))
                
                if prev_balance is not None:
                    # 检查余额是否合理（这里只做简单检查，不要求完全匹配）
                    # 因为不同银行的余额计算方式可能不同
                    if balance < Decimal("0") and abs(balance) > Decimal("10000000"):
                        balance_errors.append({
                            "row_index": idx,
                            "error": f"余额异常: {balance}",
                            "warning": True
                        })
                
                prev_balance = balance
            except Exception as e:
                balance_errors.append({
                    "row_index": idx,
                    "error": f"余额格式错误: {balance_str}, {str(e)}"
                })
        
        if balance_errors:
            validation_results["checks"]["balance_continuity"] = False
            # 只保留错误，不保留警告
            validation_results["errors"].extend([e for e in balance_errors if not e.get("warning")])
            validation_results["warnings"].extend([e for e in balance_errors if e.get("warning")])
        
        # 验证3：总金额平衡检查
        amount_errors = []
        total_income = Decimal("0")
        total_expense = Decimal("0")
        total_balance_change = Decimal("0")
        
        for idx, tx in enumerate(transactions_list):
            amount_str = tx.get("金额", "0")
            income_expense = tx.get("收支类型", "")
            
            if not amount_str or str(amount_str).strip() == "":
                amount_errors.append({
                    "row_index": idx,
                    "error": "金额字段为空"
                })
                continue
            
            try:
                amount = Decimal(str(amount_str))
                
                if income_expense == "收入":
                    total_income += amount
                    total_balance_change += amount
                elif income_expense == "支出":
                    total_expense += amount
                    total_balance_change -= amount
                
            except Exception as e:
                amount_errors.append({
                    "row_index": idx,
                    "error": f"金额格式错误: {amount_str}, {str(e)}"
                })
        
        if amount_errors:
            validation_results["checks"]["amount_balance"] = False
            validation_results["errors"].extend(amount_errors)
        
        # 计算期末余额 - 期初余额
        if len(transactions_list) >= 2:
            try:
                first_balance = Decimal(str(transactions_list[0].get("余额", "0")))
                last_balance = Decimal(str(transactions_list[-1].get("余额", "0")))
                expected_change = last_balance - first_balance
                
                # 允许0.01元的误差
                diff = abs(total_balance_change - expected_change)
                if diff > Decimal("0.01"):
                    validation_results["checks"]["amount_balance"] = False
                    validation_results["errors"].append({
                        "error": f"金额不平衡。计算总变化: {total_balance_change}, 实际余额变化: {expected_change}, 差异: {diff}",
                        "total_income": float(total_income),
                        "total_expense": float(total_expense),
                        "calculated_change": float(total_balance_change),
                        "actual_change": float(expected_change)
                    })
            except Exception as e:
                validation_results["checks"]["amount_balance"] = False
                validation_results["errors"].append({
                    "error": f"金额平衡检查失败: {str(e)}"
                })
        
        # 验证4：时间顺序检查（可选）
        time_errors = []
        prev_time = None
        
        for idx, tx in enumerate(transactions_list):
            time_str = tx.get("交易时间", "")
            if not time_str:
                continue
            
            if prev_time and time_str < prev_time:
                time_errors.append({
                    "row_index": idx,
                    "error": f"时间顺序异常: {time_str} < {prev_time}",
                    "warning": True
                })
            
            prev_time = time_str
        
        if time_errors:
            validation_results["checks"]["time_order"] = False
            validation_results["warnings"].extend(time_errors)
        
        # 汇总验证结果
        if validation_results["errors"]:
            validation_results["success"] = False
            validation_results["valid_rows"] = validation_results["total_rows"] - len(validation_results["errors"])
        else:
            validation_results["valid_rows"] = validation_results["total_rows"]
        
        return json.dumps(validation_results, ensure_ascii=False, indent=2)
        
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@tool
def validate_json_format(data: str) -> str:
    """
    验证JSON格式是否正确
    
    Args:
        data: JSON字符串
        
    Returns:
        JSON字符串，包含验证结果
    """
    try:
        parsed = json.loads(data)
        result = {
            "success": True,
            "message": "JSON格式正确",
            "type": type(parsed).__name__
        }
        return json.dumps(result, ensure_ascii=False)
    except json.JSONDecodeError as e:
        result = {
            "success": False,
            "error": f"JSON格式错误: {str(e)}",
            "line": e.lineno,
            "column": e.colno
        }
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        result = {
            "success": False,
            "error": f"验证失败: {str(e)}"
        }
        return json.dumps(result, ensure_ascii=False)


@tool
def calculate_summary_statistics(transactions: str) -> str:
    """
    计算汇总统计信息
    
    Args:
        transactions: JSON字符串格式的交易数据数组
        
    Returns:
        JSON字符串，包含统计信息
    """
    try:
        transactions_list = json.loads(transactions)
        
        if not isinstance(transactions_list, list):
            return json.dumps({"error": "输入格式错误"}, ensure_ascii=False)
        
        total_income = 0.0
        total_expense = 0.0
        transaction_count = len(transactions_list)
        income_count = 0
        expense_count = 0
        other_count = 0
        
        transaction_types = {}
        transaction_methods = {}
        
        for tx in transactions_list:
            amount = float(tx.get("金额", "0"))
            income_expense = tx.get("收支类型", "其他")
            
            if income_expense == "收入":
                total_income += amount
                income_count += 1
            elif income_expense == "支出":
                total_expense += amount
                expense_count += 1
            else:
                other_count += 1
            
            # 统计交易类型
            tx_type = tx.get("交易类型", "其他")
            transaction_types[tx_type] = transaction_types.get(tx_type, 0) + 1
            
            # 统计交易方式
            tx_method = tx.get("交易方式", "")
            if tx_method:
                transaction_methods[tx_method] = transaction_methods.get(tx_method, 0) + 1
        
        # 时间范围
        time_range = {
            "start": "",
            "end": ""
        }
        
        if transactions_list:
            first_time = transactions_list[0].get("交易时间", "")
            last_time = transactions_list[-1].get("交易时间", "")
            if first_time:
                time_range["start"] = first_time
            if last_time:
                time_range["end"] = last_time
        
        summary = {
            "transaction_count": transaction_count,
            "income_count": income_count,
            "expense_count": expense_count,
            "other_count": other_count,
            "total_income": round(total_income, AMOUNT_PRECISION),
            "total_expense": round(total_expense, AMOUNT_PRECISION),
            "net_amount": round(total_income - total_expense, AMOUNT_PRECISION),
            "time_range": time_range,
            "transaction_types": transaction_types,
            "transaction_methods": transaction_methods
        }
        
        return json.dumps(summary, ensure_ascii=False, indent=2)
        
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@tool
def check_required_fields(transaction: str) -> str:
    """
    检查单条交易数据是否包含所有必填字段
    
    Args:
        transaction: JSON字符串格式的交易数据
        
    Returns:
        JSON字符串，包含检查结果
    """
    try:
        tx_data = json.loads(transaction)
        
        if not isinstance(tx_data, dict):
            return json.dumps({"error": "输入格式错误，需要对象"}, ensure_ascii=False)
        
        missing_fields = []
        empty_fields = []
        
        for field in REQUIRED_FIELDS:
            if field not in tx_data:
                missing_fields.append(field)
            elif not tx_data[field] or str(tx_data[field]).strip() == "":
                empty_fields.append(field)
        
        result = {
            "valid": len(missing_fields) == 0 and len(empty_fields) == 0,
            "missing_fields": missing_fields,
            "empty_fields": empty_fields
        }
        
        return json.dumps(result, ensure_ascii=False)
        
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)
