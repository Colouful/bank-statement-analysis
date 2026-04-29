#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
银行流水解析器 - 支持PDF、Excel、CSV、图片扫描件
优化正则表达式，提高数据提取准确性
"""

import os
import re
import json
import csv
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

try:
    import pandas as pd
except ImportError:
    pd = None

try:
    from PIL import Image
    import pytesseract
except ImportError:
    Image = None
    pytesseract = None


class BankStatementParser:
    """银行流水解析器"""

    def __init__(self):
        self.standard_fields = [
            "交易时间", "收支类型", "金额", "交易对方",
            "交易备注/摘要", "交易方式", "交易类型", "余额", "其他"
        ]

        # 交易类型关键词（优化版）
        self.transaction_keywords = {
            "消费": ["消费", "购物", "买", "购", "淘宝", "天猫", "京东", "拼多多", "超市", "商城",
                     "美团", "饿了么", "外卖", "餐饮", "咖啡", "电影", "充值", "游戏", "话费",
                     "支付", "快捷支付", "扫码", "POS", "刷卡", "网购"],
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
            "手续费": ["手续费", "服务费", "工本费", "年费", "月费", "管理费"],
        }

    def parse_file(self, file_path: str) -> Dict[str, Any]:
        """
        解析银行流水文件（自动识别格式）

        Args:
            file_path: 文件路径

        Returns:
            解析结果
        """
        if not os.path.exists(file_path):
            return {"success": False, "error": f"文件不存在: {file_path}"}

        # 自动识别文件格式
        file_ext = os.path.splitext(file_path)[1].lower()

        if file_ext == '.pdf':
            return self._parse_pdf(file_path)
        elif file_ext in ['.xlsx', '.xls']:
            return self._parse_excel(file_path)
        elif file_ext == '.csv':
            return self._parse_csv(file_path)
        elif file_ext in ['.png', '.jpg', '.jpeg', '.bmp', '.tiff']:
            return self._parse_image(file_path)
        else:
            return {"success": False, "error": f"不支持的文件格式: {file_ext}"}

    def _parse_pdf(self, file_path: str) -> Dict[str, Any]:
        """解析PDF文件"""
        if pdfplumber is None:
            return {"success": False, "error": "未安装pdfplumber库"}

        try:
            with pdfplumber.open(file_path) as pdf:
                all_text = ""
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        all_text += text + "\n"

                # 提取元数据
                metadata = self._extract_metadata(all_text)

                # 提取表格数据
                headers, rows = self._extract_pdf_table_data(all_text)

                # 列名映射
                mapping = self._map_columns(headers)

                # 数据清洗
                cleaned_data = self._clean_transaction_data(rows, mapping, headers)

                return {
                    "success": True,
                    "metadata": metadata,
                    "headers": headers,
                    "rows": rows,
                    "mapping": mapping,
                    "cleaned_data": cleaned_data,
                    "total_rows": len(cleaned_data)
                }

        except Exception as e:
            return {"success": False, "error": f"PDF解析失败: {str(e)}"}

    def _parse_excel(self, file_path: str) -> Dict[str, Any]:
        """解析Excel文件"""
        if pd is None:
            return {"success": False, "error": "未安装pandas库"}

        try:
            # 读取Excel
            df = pd.read_excel(file_path, engine='openpyxl')

            # 转换为列表
            headers = df.columns.tolist()
            rows = df.values.tolist()

            # 清空值处理
            rows = [[str(cell) if pd.notna(cell) else "" for cell in row] for row in rows]

            # 提取元数据（从第一行或文件名）
            metadata = self._extract_metadata_from_excel(df)

            # 列名映射
            mapping = self._map_columns(headers)

            # 数据清洗
            cleaned_data = self._clean_transaction_data(rows, mapping, headers)

            return {
                "success": True,
                "metadata": metadata,
                "headers": headers,
                "rows": rows,
                "mapping": mapping,
                "cleaned_data": cleaned_data,
                "total_rows": len(cleaned_data)
            }

        except Exception as e:
            return {"success": False, "error": f"Excel解析失败: {str(e)}"}

    def _parse_csv(self, file_path: str) -> Dict[str, Any]:
        """解析CSV文件"""
        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                # 自动检测分隔符
                dialect = csv.Sniffer().sniff(f.read(1024))
                f.seek(0)
                reader = csv.reader(f, dialect)

                headers = next(reader)
                rows = list(reader)

            # 提取元数据
            metadata = {"bank_name": "未知", "file_type": "CSV"}

            # 列名映射
            mapping = self._map_columns(headers)

            # 数据清洗
            cleaned_data = self._clean_transaction_data(rows, mapping, headers)

            return {
                "success": True,
                "metadata": metadata,
                "headers": headers,
                "rows": rows,
                "mapping": mapping,
                "cleaned_data": cleaned_data,
                "total_rows": len(cleaned_data)
            }

        except Exception as e:
            return {"success": False, "error": f"CSV解析失败: {str(e)}"}

    def _parse_image(self, file_path: str) -> Dict[str, Any]:
        """解析图片扫描件（OCR）"""
        if Image is None or pytesseract is None:
            return {"success": False, "error": "未安装PIL或pytesseract库"}

        try:
            # OCR识别
            image = Image.open(file_path)
            text = pytesseract.image_to_string(image, lang='chi_sim+eng')

            # 提取元数据
            metadata = self._extract_metadata(text)

            # 提取表格数据
            headers, rows = self._extract_pdf_table_data(text)

            # 列名映射
            mapping = self._map_columns(headers)

            # 数据清洗
            cleaned_data = self._clean_transaction_data(rows, mapping, headers)

            return {
                "success": True,
                "metadata": metadata,
                "headers": headers,
                "rows": rows,
                "mapping": mapping,
                "cleaned_data": cleaned_data,
                "total_rows": len(cleaned_data),
                "ocr_text": text[:500]  # 保留前500字符用于调试
            }

        except Exception as e:
            return {"success": False, "error": f"OCR解析失败: {str(e)}"}

    def _extract_metadata(self, text: str) -> Dict[str, Any]:
        """从文本中提取元数据"""
        metadata = {
            "account_name": "",
            "account_no": "",
            "idcard": "",
            "bank_name": "",
            "time_range": {"start": "", "end": ""},
            "currency": "人民币"
        }

        # 提取账户名
        account_name_match = re.search(r'户名[：:]\s*([^\s\n]+)', text)
        if account_name_match:
            metadata["account_name"] = account_name_match.group(1)

        # 提取账号
        account_no_match = re.search(r'账号[：:]\s*([0-9]+)', text)
        if account_no_match:
            metadata["account_no"] = account_no_match.group(1)

        # 提取证件号
        idcard_match = re.search(r'证件号码[：:]\s*([0-9X]+)', text)
        if idcard_match:
            metadata["idcard"] = idcard_match.group(1)

        # 提取银行名称
        bank_keywords = {
            "中国工商银行": "工商银行",
            "中国建设银行": "建设银行",
            "中国农业银行": "农业银行",
            "中国银行": "中国银行",
            "中信银行": "中信银行",
            "招商银行": "招商银行",
            "浦发银行": "浦发银行",
            "交通银行": "交通银行",
            "平安银行": "平安银行",
        }

        for bank, short_name in bank_keywords.items():
            if bank in text:
                metadata["bank_name"] = short_name
                break

        return metadata

    def _extract_metadata_from_excel(self, df) -> Dict[str, Any]:
        """从Excel提取元数据"""
        metadata = {
            "account_name": "",
            "account_no": "",
            "bank_name": "",
            "time_range": {"start": "", "end": ""},
            "currency": "人民币"
        }

        # 尝试从第一列或第一行提取信息
        for idx, row in df.head(10).iterrows():
            for col in df.columns:
                value = str(row[col])
                if '账户' in value and ':' in value:
                    parts = value.split(':')
                    if len(parts) > 1:
                        metadata["account_no"] = parts[1].strip()

        return metadata

    def _extract_pdf_table_data(self, text: str) -> Tuple[List[str], List[List[str]]]:
        """
        从PDF文本中提取表格数据（优化版正则表达式）

        Returns:
            (headers, rows)
        """
        lines = text.split('\n')

        # 找到表头行
        header_idx = None
        header_line = None

        for i, line in enumerate(lines):
            if '交易日期' in line and ('收入金额' in line or '金额' in line):
                header_idx = i
                header_line = line
                break

        if not header_line:
            return [], []

        # 提取列名
        headers = header_line.split()

        # 提取数据行（改进的正则表达式）
        rows = []
        for i in range(header_idx + 1, len(lines)):
            line = lines[i].strip()

            # 跳过空行和太短的行
            if not line or len(line) < 10:
                continue

            # 跳过标题行、英文说明行
            if 'Transaction' in line or 'Account' in line or 'Description' in line:
                continue

            # 检查是否以日期开头
            if not line[:8].isdigit():
                continue

            # 改进的正则表达式：精确匹配交易数据
            # 使用更灵活的匹配方式
            parts = []

            # 提取日期（前8位）
            date_part = line[:8]
            parts.append(date_part)

            # 剩余部分
            remaining = line[8:].strip()

            # 查找所有的 "RMB xxx.xx" 模式
            rmb_pattern = r'RMB\s+([\d.]+)'
            amounts = re.findall(rmb_pattern, remaining)

            # 移除已匹配的RMB部分
            remaining = re.sub(rmb_pattern, '', remaining).strip()

            # 填充收入、支出、余额
            # 根据上下文判断：通常第1个是收入，第2个是支出，第3个是余额
            income = amounts[0] if len(amounts) > 0 else ""
            expense = amounts[1] if len(amounts) > 1 else ""
            balance = amounts[2] if len(amounts) > 2 else ""

            parts.append(income)
            parts.append(expense)
            parts.append(balance)

            # 剩余部分就是摘要、账号、户名
            # 尝试识别账号（纯数字）
            account_pattern = r'\s+(\d{10,})\s+'
            account_match = re.search(account_pattern, remaining)

            if account_match:
                account = account_match.group(1)
                # 分割：账号之前是摘要，账号之后是户名
                account_idx = remaining.find(account)
                summary = remaining[:account_idx].strip()
                name = remaining[account_idx + len(account):].strip()
            else:
                # 没有账号，全部作为摘要
                summary = remaining.strip()
                account = ""
                name = ""

            parts.append(summary)
            parts.append(account)
            parts.append(name)

            # 清理和验证
            parts = [p.strip() if p else "" for p in parts]

            # 确保至少有金额数据
            if income or expense or balance:
                rows.append(parts)

        return headers, rows

    def _map_columns(self, headers: List[str]) -> Dict[str, str]:
        """列名映射"""
        mapping = {}

        for header in headers:
            header_lower = header.lower()

            if '交易日期' in header or '日期' in header or 'date' in header_lower:
                mapping[header] = '交易时间'
            elif '收入金额' in header or '收入' in header:
                mapping[header] = '收支类型'
            elif '支出金额' in header or '支出' in header:
                mapping[header] = '收支类型'
            elif '金额' in header:
                mapping[header] = '金额'
            elif '账户余额' in header or '余额' in header or 'balance' in header_lower:
                mapping[header] = '余额'
            elif '交易摘要' in header or '摘要' in header:
                mapping[header] = '交易备注/摘要'
            elif '对方账号' in header or '账号' in header:
                mapping[header] = '交易对方'
            elif '对方户名' in header or '户名' in header:
                mapping[header] = '交易对方'

        return mapping

    def _clean_transaction_data(self, rows: List[List[str]], mapping: Dict[str, str],
                                headers: List[str]) -> List[Dict[str, Any]]:
        """清洗交易数据"""
        cleaned_data = []

        # 构建列索引映射
        col_index_map = {col: idx for idx, col in enumerate(headers)}

        # 反向映射：标准字段 -> 银行列名列表
        reverse_mapping = {}
        for bank_col, std_field in mapping.items():
            if std_field not in reverse_mapping:
                reverse_mapping[std_field] = []
            reverse_mapping[std_field].append(bank_col)

        for row in rows:
            try:
                cleaned_row = {}
                other_data = {}

                # 提取各个字段
                # 交易时间
                cleaned_row['交易时间'] = self._parse_time(row[0] if len(row) > 0 else "")

                # 金额和收支类型（处理收入/支出两列）
                income_amount = 0.0
                expense_amount = 0.0
                final_amount = 0.0
                income_expense_type = None

                # 检查列名，确定收入列和支出列的索引
                income_col_idx = None
                expense_col_idx = None
                balance_col_idx = None

                for idx, header in enumerate(headers):
                    if '收入' in header and '金额' in header:
                        income_col_idx = idx
                    elif '支出' in header and '金额' in header:
                        expense_col_idx = idx
                    elif '余额' in header:
                        balance_col_idx = idx

                # 提取收入金额
                if income_col_idx is not None and income_col_idx < len(row):
                    income_amount = self._parse_amount(row[income_col_idx])

                # 提取支出金额
                if expense_col_idx is not None and expense_col_idx < len(row):
                    expense_amount = self._parse_amount(row[expense_col_idx])

                # 判断使用哪个金额和收支类型
                # 优先判断支出
                if expense_amount > 0:
                    final_amount = expense_amount
                    income_expense_type = '支出'
                elif income_amount > 0:
                    final_amount = income_amount
                    income_expense_type = '收入'
                else:
                    # 尝试从余额列或其他方式提取
                    final_amount = 0.0
                    income_expense_type = '其他'

                cleaned_row['金额'] = f"{final_amount:.2f}"
                cleaned_row['收支类型'] = income_expense_type

                # 余额
                if balance_col_idx is not None and balance_col_idx < len(row):
                    cleaned_row['余额'] = f"{self._parse_amount(row[balance_col_idx]):.2f}"
                else:
                    cleaned_row['余额'] = ""

                # 交易摘要
                summary_idx = None
                for idx, header in enumerate(headers):
                    if '摘要' in header:
                        summary_idx = idx
                        break

                if summary_idx is not None and summary_idx < len(row):
                    cleaned_row['交易备注/摘要'] = row[summary_idx]
                else:
                    cleaned_row['交易备注/摘要'] = ""

                # 交易对方
                account_idx = None
                for idx, header in enumerate(headers):
                    if '账号' in header or '户名' in header:
                        account_idx = idx
                        break

                if account_idx is not None and account_idx < len(row):
                    cleaned_row['交易对方'] = row[account_idx]
                else:
                    cleaned_row['交易对方'] = ""

                # 交易方式
                cleaned_row['交易方式'] = self._infer_transaction_method(
                    cleaned_row.get('交易备注/摘要', '')
                )

                # 交易类型
                cleaned_row['交易类型'] = self._infer_transaction_type(
                    cleaned_row.get('交易备注/摘要', ''),
                    cleaned_row.get('交易方式', ''),
                    income_expense_type
                )

                # 其他字段
                cleaned_row['其他'] = {}

                cleaned_data.append(cleaned_row)

            except Exception as e:
                # 跳过错误行，继续处理
                continue

        return cleaned_data

    def _parse_amount(self, amount_str: str) -> float:
        """解析金额字符串"""
        if not amount_str:
            return 0.0

        # 移除逗号、空格、RMB等
        amount_str = amount_str.replace(',', '').replace(' ', '').replace('RMB', '').strip()

        # 提取数字
        match = re.search(r'[\d.]+', amount_str)
        if match:
            try:
                return float(match.group())
            except ValueError:
                return 0.0

        return 0.0

    def _parse_time(self, time_str: str) -> str:
        """解析时间字符串"""
        if not time_str:
            return ""

        time_str = str(time_str).strip()

        # 如果是8位数字，转换为YYYY-MM-DD格式
        if re.match(r'^\d{8}$', time_str):
            return f"{time_str[:4]}-{time_str[4:6]}-{time_str[6:8]}"

        # 如果已经是YYYY-MM-DD格式，直接返回
        if re.match(r'^\d{4}-\d{2}-\d{2}', time_str):
            return time_str[:10]

        return time_str

    def _infer_transaction_method(self, summary: str) -> str:
        """推断交易方式"""
        if not summary:
            return ""

        summary = str(summary)

        methods = {
            "快捷支付": "快捷支付",
            "支付宝": "支付宝",
            "财付通": "财付通",
            "微信": "微信",
            "网上银行": "网上银行",
            "手机银行": "手机银行",
            "ATM": "ATM",
            "POS": "POS",
            "柜台": "柜台",
        }

        for method, key in methods.items():
            if method in summary:
                return method

        return summary

    def _infer_transaction_type(self, summary: str, method: str,
                                income_expense: Optional[str] = None) -> str:
        """推断交易类型（优化版）"""
        if not summary:
            return "其他"

        summary = str(summary).lower()

        # 根据收支类型过滤
        if income_expense == "收入":
            keywords = {k: v for k, v in self.transaction_keywords.items()
                       if k in ["工资", "理财", "转账", "退款"]}
        elif income_expense == "支出":
            keywords = {k: v for k, v in self.transaction_keywords.items()
                       if k not in ["工资", "退款"]}
        else:
            keywords = self.transaction_keywords

        # 匹配关键词
        for t_type, kw_list in keywords.items():
            for kw in kw_list:
                if kw in summary or kw.lower() in summary:
                    return t_type

        return "其他"

    def to_json(self, file_path: str) -> Dict[str, Any]:
        """解析并返回JSON格式"""
        result = self.parse_file(file_path)

        if not result or not isinstance(result, dict):
            return {"success": False, "error": "解析返回值格式错误"}

        if not result.get('success'):
            return result

        # 组装最终结果
        final_result = {
            "success": True,
            "metadata": result.get('metadata', {}),
            "orgColumns": result.get('headers', []),
            "allRows": result.get('rows', []),
            "processedColumnNameMappingData": result.get('cleaned_data', [])
        }

        return final_result


def main():
    """主函数 - 快速测试"""
    import sys

    if len(sys.argv) < 2:
        print("用法: python bank_statement_parser.py <文件路径>")
        print("支持格式: PDF, Excel (.xlsx, .xls), CSV, 图片 (.png, .jpg, .jpeg)")
        return

    file_path = sys.argv[1]
    parser = BankStatementParser()

    print(f"正在解析文件: {file_path}")
    print("=" * 60)

    result = parser.to_json(file_path)

    if result and 'success' in result and result['success']:
        print("✅ 解析成功!")
        print(f"   银行: {result['metadata'].get('bank_name', '未知')}")
        print(f"   账户: {result['metadata'].get('account_no', '未知')}")
        print(f"   列数: {len(result['orgColumns'])}")
        print(f"   行数: {len(result['processedColumnNameMappingData'])}")

        # 显示前3行
        if result['processedColumnNameMappingData']:
            print("\n前3笔交易:")
            for i, row in enumerate(result['processedColumnNameMappingData'][:3]):
                print(f"\n  第{i+1}笔:")
                print(f"    时间: {row.get('交易时间')}")
                print(f"    类型: {row.get('收支类型')} | 金额: {row.get('金额')}")
                print(f"    摘要: {row.get('交易备注/摘要')}")
                print(f"    对方: {row.get('交易对方')}")

        # 保存结果
        output_path = '/tmp/bank_statement_result.json'
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        print(f"\n✅ 结果已保存到: {output_path}")

    else:
        error_msg = result.get('error', '未知错误') if isinstance(result, dict) else str(result)
        print(f"❌ 解析失败: {error_msg}")


if __name__ == '__main__':
    main()
