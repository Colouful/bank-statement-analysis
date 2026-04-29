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
from tools.error_handler import DataCleaningError, format_error_response


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
    method_col: Optional[str],
    income_expense: Optional[str] = None
) -> str:
    """
    推断交易类型（优先级 A > B > C）

    Args:
        transaction_type_col: 交易类型列的值
        summary_col: 摘要列的值
        method_col: 交易方式列的值
        income_expense: 收支类型（收入/支出）

    Returns:
        推断出的交易类型
    """
    # 扩展的交易类型关键词映射
    TRANSACTION_KEYWORDS = {
        "消费": ["消费", "购物", "买", "购", "淘宝", "天猫", "京东", "拼多多", "超市", "商城",
                 "美团", "饿了么", "外卖", "餐饮", "咖啡", "电影", "充值", "游戏", "话费",
                 "购物", "支付", "快捷支付", "扫码", "POS", "刷卡", "网购", "商城", "店铺"],
        "转账": ["转账", "汇款", "汇兑", "转账汇款", "网银转账", "手机转账", "ATM转账",
                 "跨行转账", "行内转账", "实时转账", "普通汇兑", "汇入", "汇出"],
        "工资": ["工资", "代发", "薪酬", "薪资", "奖金", "津贴", "补助", "年终奖",
                 "发放工资", "代发工资", "工资发放", "薪酬发放"],
        "还款": ["还款", "信用卡还款", "贷款还款", "花呗", "借呗", "白条", "分期",
                 "信用卡", "贷记卡", "信贷", "逾期", "账单", "分期付款"],
        "理财": ["理财", "基金", "股票", "投资", "理财购买", "基金申购", "理财赎回",
                 "收益", "利息", "分红", "净值", "申购", "赎回"],
        "提现": ["提现", "取现", "ATM取款", "取款", "现金", "领款", "现金提取"],
        "充值": ["充值", "话费充值", "手机充值", "流量充值", "电费充值", "充值卡",
                 "钱包充值", "零钱充值", "支付宝充值", "微信充值"],
        "退款": ["退款", "退货", "取消", "退费", "撤销", "退款成功", "退款到账"],
        "代扣": ["代扣", "自动扣款", "自动扣费", "协议扣款", "定期扣款", "扣费",
                 "月费", "年费", "服务费", "管理费"],
        "利息": ["利息", "存款利息", "活期利息", "定期利息", "利息收入", "利息支出",
                 "结息", "计息"],
        "手续费": ["手续费", "服务费", "工本费", "年费", "月费", "管理费",
                   "转账手续费", "取款手续费", "汇款手续费"],
        "代付": ["代付", "代发", "代扣代付", "批量代付", "委托付款"],
        "红包": ["红包", "转账红包", "现金红包", "福利红包", "红包收入", "红包支出"],
        "奖励": ["奖励", "返现", "优惠", "补贴", "红包", "积分", "返利", "佣金"],
        "保险": ["保险", "保费", "寿险", "财险", "医疗保险", "意外险", "理赔"],
        "公积金": ["公积金", "住房公积金", "社保", "社保公积金", "社保缴费"],
        "税": ["税", "税款", "个税", "所得税", "增值税", "税费", "税务"],
        "房租": ["房租", "租金", "押金", "房费", "住房", "租赁"],
        "交通": ["交通", "打车", "滴滴", "Uber", "出租车", "地铁", "公交",
                 "加油", "ETC", "高速费", "停车费", "车辆"],
        "医疗": ["医疗", "医院", "药店", "医保", "体检", "药品", "看病"],
        "餐饮": ["餐饮", "吃饭", "外卖", "美团", "饿了么", "快餐", "美食"],
    }

    # 根据收支类型排除一些不可能的交易类型
    if income_expense == "收入":
        # 收入类可能的交易类型
        income_keywords = {k: v for k, v in TRANSACTION_KEYWORDS.items()
                         if k in ["工资", "理财", "利息", "转账", "红包", "奖励", "退款", "代付"]}
        TRANSACTION_KEYWORDS = income_keywords

    # 优先级A：从交易类型列提取
    if transaction_type_col:
        for t_type, keywords in TRANSACTION_KEYWORDS.items():
            if t_type in str(transaction_type_col):
                return t_type

    # 优先级B：从摘要推断（更智能的匹配）
    if summary_col:
        summary_lower = str(summary_col).lower()
        for t_type, keywords in TRANSACTION_KEYWORDS.items():
            for keyword in keywords:
                if keyword in summary_lower or keyword.lower() in summary_lower:
                    return t_type

    # 优先级C：从交易方式推断
    if method_col:
        method_lower = str(method_col).lower()
        for t_type, keywords in TRANSACTION_KEYWORDS.items():
            for keyword in keywords:
                if keyword in method_lower or keyword.lower() in method_lower:
                    return t_type

    # 根据收支类型和常见的交易方式做二次推断
    if income_expense and method_col:
        method_lower = str(method_col).lower()
        if income_expense == "收入":
            if "工资" in method_lower or "代发" in method_lower:
                return "工资"
            elif "转账" in method_lower or "汇入" in method_lower:
                return "转账"
            elif "理财" in method_lower or "基金" in method_lower:
                return "理财"
        elif income_expense == "支出":
            if "消费" in method_lower or "购物" in method_lower:
                return "消费"
            elif "还款" in method_lower or "信用卡" in method_lower:
                return "还款"
            elif "充值" in method_lower:
                return "充值"
            elif "提现" in method_lower or "取款" in method_lower:
                return "提现"

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
        errors = []
        
        for row_idx, row in enumerate(rows_list):
            try:
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
                    
                    # 特殊处理：如果同时有"收入金额"和"支出金额"两列
                    elif std_field == "金额":
                        # 检查是否有收入/支出两列
                        income_col = None
                        expense_col = None
                        for bank_col in bank_cols:
                            if "收入" in bank_col or "Income" in bank_col or "in" in bank_col.lower():
                                income_col = bank_col
                            elif "支出" in bank_col or "Expense" in bank_col or "out" in bank_col.lower():
                                expense_col = bank_col

                        # 提取收入和支出金额
                        income_amount = 0.0
                        expense_amount = 0.0
                        final_amount = 0.0
                        final_income_expense = None

                        # 从收入列提取
                        if income_col and income_col in col_index_map:
                            idx = col_index_map[income_col]
                            if idx < len(row):
                                income_val = row[idx]
                                if income_val and str(income_val).strip():
                                    income_amount, _ = _parse_amount(str(income_val))

                        # 从支出列提取
                        if expense_col and expense_col in col_index_map:
                            idx = col_index_map[expense_col]
                            if idx < len(row):
                                expense_val = row[idx]
                                if expense_val and str(expense_val).strip():
                                    expense_amount, _ = _parse_amount(str(expense_val))

                        # 判断使用哪个金额
                        if income_amount > 0:
                            final_amount = income_amount
                            final_income_expense = "收入"
                        elif expense_amount > 0:
                            final_amount = expense_amount
                            final_income_expense = "支出"
                        else:
                            # 两列都为空，尝试从普通金额列提取
                            amount, income_expense = _parse_amount(field_value) if field_value else (0.0, None)
                            final_amount = amount
                            final_income_expense = income_expense

                        cleaned_row[std_field] = f"{final_amount:.{AMOUNT_PRECISION}f}"
                        # 如果收支类型列没有值，从金额推断
                        if final_income_expense and not cleaned_row.get("收支类型"):
                            cleaned_row["收支类型"] = final_income_expense
                    
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
                    cleaned_row.get("交易方式"),
                    cleaned_row.get("收支类型")
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
                
            except Exception as e:
                # 记录单行错误，但不中断整个处理
                error_info = {
                    "row_index": row_idx,
                    "row_data": row[:10] if len(row) > 10 else row,  # 只保留前10列避免过长
                    "error": str(e),
                    "error_type": type(e).__name__
                }
                errors.append(error_info)
                continue
        
        result = {
            "success": True,
            "cleaned_data": cleaned_data,
            "total_rows": len(cleaned_data),
            "total_processed": len(rows_list),
            "error_count": len(errors)
        }
        
        # 如果有错误，添加到结果中
        if errors:
            result["errors"] = errors
            result["warnings"] = [
                f"共有 {len(errors)} 行数据清洗失败，已跳过这些行"
            ]
        
        return json.dumps(result, ensure_ascii=False, indent=2)
        
    except json.JSONDecodeError as e:
        error_info = format_error_response(
            DataCleaningError(f"JSON解析失败: {str(e)}", details=f"输入数据格式不正确")
        )
        return json.dumps(error_info, ensure_ascii=False)
    except KeyError as e:
        error_info = format_error_response(
            DataCleaningError(f"缺少必要的列: {str(e)}", details="列名映射中缺少必要的字段")
        )
        return json.dumps(error_info, ensure_ascii=False)
    except IndexError as e:
        error_info = format_error_response(
            DataCleaningError(f"数据行长度不匹配: {str(e)}", details="数据行列数与列名不匹配")
        )
        return json.dumps(error_info, ensure_ascii=False)
    except ValueError as e:
        error_info = format_error_response(
            DataCleaningError(f"数据格式错误: {str(e)}", details="金额或时间字段格式不正确")
        )
        return json.dumps(error_info, ensure_ascii=False)
    except Exception as e:
        error_info = format_error_response(
            DataCleaningError(f"未知错误: {str(e)}", details=type(e).__name__)
        )
        return json.dumps(error_info, ensure_ascii=False)


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
