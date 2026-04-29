#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
回归测试脚本
测试所有格式和边界情况
"""

import sys
import time
import json
from bank_statement_parser import BankStatementParser


class TestResult:
    """测试结果"""
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
        self.performance = {}

    def record_pass(self, test_name, duration):
        """记录通过"""
        self.passed += 1
        self.performance[test_name] = duration
        print(f"✅ {test_name}: 通过 ({duration:.2f}秒)")

    def record_fail(self, test_name, reason):
        """记录失败"""
        self.failed += 1
        self.errors.append({"test": test_name, "reason": reason})
        print(f"❌ {test_name}: 失败 - {reason}")

    def summary(self):
        """测试总结"""
        print("\n" + "=" * 60)
        print("测试总结")
        print("=" * 60)
        print(f"通过: {self.passed}")
        print(f"失败: {self.failed}")
        print(f"总数: {self.passed + self.failed}")

        if self.performance:
            avg_time = sum(self.performance.values()) / len(self.performance)
            print(f"\n平均耗时: {avg_time:.2f}秒")

        if self.errors:
            print("\n失败详情:")
            for error in self.errors:
                print(f"  - {error['test']}: {error['reason']}")

        return self.failed == 0


def test_pdf_parsing(parser, result):
    """测试PDF解析"""
    print("\n【测试1】PDF文件解析")
    start_time = time.time()

    test_file = "assets/fa72fa84489945c5ac6bbba086307244.pdf.pdf"
    parse_result = parser.parse_file(test_file)
    duration = time.time() - start_time

    if not parse_result.get('success'):
        result.record_fail("PDF解析", parse_result.get('error'))
        return

    # 验证基本字段
    checks = [
        ('银行名称', parse_result.get('metadata', {}).get('bank_name') == '中信银行'),
        ('账户号', len(parse_result.get('metadata', {}).get('account_no', '')) > 0),
        ('列名数量', len(parse_result.get('headers', [])) == 7),
        ('交易数量', parse_result.get('total_rows', 0) > 0),
        ('清洗数据', len(parse_result.get('cleaned_data', [])) > 0),
    ]

    all_passed = True
    for check_name, check_result in checks:
        if not check_result:
            result.record_fail(f"PDF-{check_name}", "验证失败")
            all_passed = False

    if all_passed:
        result.record_pass("PDF解析", duration)


def test_csv_parsing(parser, result):
    """测试CSV解析"""
    print("\n【测试2】CSV文件解析")
    start_time = time.time()

    test_file = "test_data/bank_statement_test.csv"
    parse_result = parser.parse_file(test_file)
    duration = time.time() - start_time

    if not parse_result.get('success'):
        result.record_fail("CSV解析", parse_result.get('error'))
        return

    # 验证数据
    cleaned_data = parse_result.get('cleaned_data', [])
    if len(cleaned_data) != 5:
        result.record_fail("CSV-数据量", f"期望5行，实际{len(cleaned_data)}行")
        return

    # 验证收支类型
    income_count = sum(1 for row in cleaned_data if row.get('收支类型') == '收入')
    expense_count = sum(1 for row in cleaned_data if row.get('收支类型') == '支出')

    if income_count != 1 or expense_count != 4:
        result.record_fail("CSV-收支类型", f"收入{income_count}/支出{expense_count}，期望1/4")
        return

    result.record_pass("CSV解析", duration)


def test_excel_parsing(parser, result):
    """测试Excel解析"""
    print("\n【测试3】Excel文件解析")
    start_time = time.time()

    test_file = "test_data/bank_statement_test.xlsx"
    parse_result = parser.parse_file(test_file)
    duration = time.time() - start_time

    if not parse_result.get('success'):
        result.record_fail("Excel解析", parse_result.get('error'))
        return

    # 验证数据
    cleaned_data = parse_result.get('cleaned_data', [])
    if len(cleaned_data) != 7:
        result.record_fail("Excel-数据量", f"期望7行，实际{len(cleaned_data)}行")
        return

    # 验证边界数据
    # 第2行应该是0.01的最小金额
    if abs(float(cleaned_data[1].get('金额', 0)) - 0.01) > 0.001:
        result.record_fail("Excel-最小金额", "0.01解析错误")
        return

    # 第4行应该是大金额
    if abs(float(cleaned_data[3].get('金额', 0)) - 1234567.89) > 0.01:
        result.record_fail("Excel-大金额", "大金额解析错误")
        return

    result.record_pass("Excel解析", duration)


def test_edge_cases(parser, result):
    """测试边界情况"""
    print("\n【测试4】边界情况测试")
    start_time = time.time()

    test_file = "test_data/bank_statement_test.xlsx"
    parse_result = parser.parse_file(test_file)
    duration = time.time() - start_time

    if not parse_result.get('success'):
        result.record_fail("边界测试", parse_result.get('error'))
        return

    cleaned_data = parse_result.get('cleaned_data', [])

    # 测试1：空日期处理
    row_with_empty_date = cleaned_data[5]  # 第6行有空日期
    if row_with_empty_date.get('交易时间') != "":
        result.record_fail("边界-空日期", "空日期未正确处理")
        return

    # 测试2：只有收入的情况
    row_with_income_only = cleaned_data[2]  # 第3行只有收入
    if row_with_income_only.get('收支类型') != '收入':
        result.record_fail("边界-只有收入", "只有收入的行未正确识别")
        return

    # 测试3：大金额精度
    row_with_large_amount = cleaned_data[3]  # 第4行大金额
    amount = float(row_with_large_amount.get('金额', 0))
    if abs(amount - 1234567.89) > 0.01:
        result.record_fail("边界-大金额精度", f"期望1234567.89，实际{amount}")
        return

    # 测试4：空值处理
    row_with_empty_value = cleaned_data[1]  # 第2行有空户名
    if row_with_empty_value.get('交易对方') != "":
        result.record_fail("边界-空值", "空值未正确处理")
        return

    result.record_pass("边界情况", duration)


def test_transaction_type_inference(parser, result):
    """测试交易类型推断"""
    print("\n【测试5】交易类型推断")
    start_time = time.time()

    test_file = "test_data/bank_statement_test.csv"
    parse_result = parser.parse_file(test_file)
    duration = time.time() - start_time

    if not parse_result.get('success'):
        result.record_fail("交易类型推断", parse_result.get('error'))
        return

    cleaned_data = parse_result.get('cleaned_data', [])

    # 验证消费类（"消费"应该匹配到消费类型）
    row_1 = cleaned_data[0]
    if row_1.get('交易类型') != '消费':
        result.record_fail("交易类型-消费", f"期望'消费'，实际'{row_1.get('交易类型')}'")
        return

    # 验证工资类
    row_3 = cleaned_data[2]
    if row_3.get('交易类型') != '工资':
        result.record_fail("交易类型-工资", f"期望'工资'，实际'{row_3.get('交易类型')}'")
        return

    result.record_pass("交易类型推断", duration)


def test_performance(parser, result):
    """测试性能"""
    print("\n【测试6】性能测试")
    start_time = time.time()

    test_file = "assets/fa72fa84489945c5ac6bbba086307244.pdf.pdf"
    parse_result = parser.parse_file(test_file)
    duration = time.time() - start_time

    if not parse_result.get('success'):
        result.record_fail("性能测试", parse_result.get('error'))
        return

    # 验证处理速度（应该在5秒内）
    if duration > 5.0:
        result.record_fail("性能测试", f"处理时间{duration:.2f}秒超过5秒限制")
        return

    # 验证数据处理量
    total_rows = parse_result.get('total_rows', 0)
    if total_rows < 400:  # 应该有480行
        result.record_fail("性能测试", f"数据处理量不足，只有{total_rows}行")
        return

    result.record_pass("性能测试", duration)


def test_accuracy(parser, result):
    """测试准确性"""
    print("\n【测试7】准确性测试")
    start_time = time.time()

    test_file = "test_data/bank_statement_test.csv"
    parse_result = parser.parse_file(test_file)
    duration = time.time() - start_time

    if not parse_result.get('success'):
        result.record_fail("准确性测试", parse_result.get('error'))
        return

    cleaned_data = parse_result.get('cleaned_data', [])

    # 验证金额准确性
    test_cases = [
        (0, 370.00, "支出"),
        (1, 45.00, "支出"),
        (2, 5000.00, "收入"),
    ]

    for idx, expected_amount, expected_type in test_cases:
        row = cleaned_data[idx]
        actual_amount = float(row.get('金额', 0))
        actual_type = row.get('收支类型')

        if abs(actual_amount - expected_amount) > 0.01:
            result.record_fail(f"准确性-第{idx+1}行金额",
                             f"期望{expected_amount}，实际{actual_amount}")
            return

        if actual_type != expected_type:
            result.record_fail(f"准确性-第{idx+1}行类型",
                             f"期望{expected_type}，实际{actual_type}")
            return

    result.record_pass("准确性测试", duration)


def test_error_handling(parser, result):
    """测试错误处理"""
    print("\n【测试8】错误处理")
    start_time = time.time()

    # 测试不存在的文件
    parse_result = parser.parse_file("non_existent_file.pdf")

    if parse_result.get('success'):
        result.record_fail("错误处理-不存在文件", "应该返回错误但返回成功")
        return

    # 测试不支持的格式
    parse_result = parser.parse_file("test_data/测试说明.txt")

    if parse_result.get('success'):
        result.record_fail("错误处理-不支持格式", "应该返回错误但返回成功")
        return

    duration = time.time() - start_time
    result.record_pass("错误处理", duration)


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("银行流水解析器 - 回归测试")
    print("=" * 60)

    parser = BankStatementParser()
    result = TestResult()

    # 运行所有测试
    test_pdf_parsing(parser, result)
    test_csv_parsing(parser, result)
    test_excel_parsing(parser, result)
    test_edge_cases(parser, result)
    test_transaction_type_inference(parser, result)
    test_performance(parser, result)
    test_accuracy(parser, result)
    test_error_handling(parser, result)

    # 生成测试报告
    success = result.summary()

    # 保存测试报告
    report = {
        "passed": result.passed,
        "failed": result.failed,
        "total": result.passed + result.failed,
        "performance": result.performance,
        "errors": result.errors,
        "success": success
    }

    report_path = "test_data/test_report.json"
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 测试报告已保存到: {report_path}")

    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(run_all_tests())
