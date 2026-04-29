#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用户验收测试脚本

使用方法:
    python user_acceptance_test.py [file_path]

示例:
    python user_acceptance_test.py                      # 测试所有示例文件
    python user_acceptance_test.py your_file.pdf         # 测试指定文件
"""

import sys
import json
import time
from pathlib import Path
from bank_statement_parser import BankStatementParser


class Color:
    """终端颜色"""
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'


def print_header(text):
    """打印标题"""
    print(f"\n{Color.BLUE}{Color.BOLD}{'=' * 80}{Color.END}")
    print(f"{Color.BLUE}{Color.BOLD}{text:^80}{Color.END}")
    print(f"{Color.BLUE}{Color.BOLD}{'=' * 80}{Color.END}\n")


def print_success(text):
    """打印成功信息"""
    print(f"{Color.GREEN}✅ {text}{Color.END}")


def print_error(text):
    """打印错误信息"""
    print(f"{Color.RED}❌ {text}{Color.END}")


def print_warning(text):
    """打印警告信息"""
    print(f"{Color.YELLOW}⚠️  {text}{Color.END}")


def print_info(text):
    """打印信息"""
    print(f"{Color.BLUE}ℹ️  {text}{Color.END}")


def test_file(file_path, parser):
    """测试单个文件"""
    print(f"\n{Color.BOLD}测试文件: {file_path}{Color.END}")
    print("-" * 80)

    start_time = time.time()

    # 检查文件是否存在
    if not Path(file_path).exists():
        print_error(f"文件不存在: {file_path}")
        return False

    # 解析文件
    result = parser.to_json(file_path)
    elapsed_time = time.time() - start_time

    if not result.get('success'):
        print_error(f"解析失败: {result.get('error')}")
        return False

    # 检查结果
    success = True

    # 1. 检查元数据（账号信息不是必须的，Excel/CSV可能没有）
    metadata = result.get('metadata', {})
    if metadata.get('account_no'):
        print_success(f"账号: {metadata.get('account_no')}")
        if metadata.get('account_name'):
            print_success(f"户名: {metadata.get('account_name')}")
        if metadata.get('bank_name'):
            print_success(f"银行: {metadata.get('bank_name')}")
    else:
        print_info("未提取到账号信息（Excel/CSV可能不包含，这是正常的）")

    # 2. 检查交易数据
    processed_data = result.get('processedColumnNameMappingData', [])
    if not processed_data:
        print_warning("未提取到交易数据")
        success = False
    else:
        print_success(f"交易笔数: {len(processed_data)}")

        # 3. 检查必填字段
        required_fields = ['交易时间', '收支类型', '金额', '余额']
        missing_fields = []
        for row in processed_data[:5]:  # 只检查前5行
            for field in required_fields:
                if not row.get(field):
                    missing_fields.append(field)

        if missing_fields:
            print_warning(f"部分记录缺少必填字段: {set(missing_fields)}")
            success = False
        else:
            print_success("必填字段完整")

    # 4. 检查交易类型
    transaction_types = set(row.get('交易类型', '') for row in processed_data if row.get('交易类型'))
    if transaction_types:
        print_success(f"识别的交易类型: {', '.join(transaction_types)}")

    # 5. 性能检查
    print_info(f"处理时间: {elapsed_time:.2f}秒")

    if elapsed_time > 10:
        print_warning(f"处理时间较长 ({elapsed_time:.2f}秒)，建议优化")
    else:
        print_success(f"性能良好")

    # 6. 显示示例数据
    if processed_data:
        print(f"\n{Color.BOLD}示例数据（前3行）:{Color.END}")
        for i, row in enumerate(processed_data[:3], 1):
            print(f"\n【第{i}行】")
            print(f"  时间: {row.get('交易时间')}")
            print(f"  类型: {row.get('收支类型')}")
            print(f"  金额: {row.get('金额')}")
            print(f"  摘要: {row.get('交易备注/摘要')}")
            print(f"  类型: {row.get('交易类型')}")
            print(f"  余额: {row.get('余额')}")

    return success


def run_acceptance_test(file_path=None):
    """运行验收测试"""
    print_header("银行流水解析器 - 用户验收测试")

    parser = BankStatementParser()

    # 如果指定了文件，只测试该文件
    if file_path:
        print_info(f"测试指定文件: {file_path}\n")
        success = test_file(file_path, parser)
    else:
        # 测试所有示例文件
        test_files = [
            # PDF文件
            'assets/fa72fa84489945c5ac6bbba086307244.pdf.pdf',

            # CSV文件
            'test_data/bank_statement_test.csv',

            # Excel文件
            'test_data/bank_statement_test.xlsx',
        ]

        print_info(f"测试文件数量: {len(test_files)}\n")

        results = []
        for file_path in test_files:
            if Path(file_path).exists():
                result = test_file(file_path, parser)
                results.append((file_path, result))
            else:
                print_warning(f"文件不存在，跳过: {file_path}")
                results.append((file_path, None))

        # 汇总结果
        print_header("测试总结")

        total = len([r for r in results if r[1] is not None])
        passed = len([r for r in results if r[1] is True])
        failed = len([r for r in results if r[1] is False])
        skipped = len([r for r in results if r[1] is None])

        print(f"总数: {total}")
        print(f"{Color.GREEN}通过: {passed}{Color.END}")
        if failed > 0:
            print(f"{Color.RED}失败: {failed}{Color.END}")
        if skipped > 0:
            print(f"{Color.YELLOW}跳过: {skipped}{Color.END}")

        success = (failed == 0 and passed > 0)

        # 失败详情
        if failed > 0:
            print(f"\n{Color.RED}失败文件:{Color.END}")
            for file_path, result in results:
                if result is False:
                    print(f"  - {file_path}")

    print(f"\n{'=' * 80}\n")

    if success:
        print_success("验收测试通过！🎉")
        print_info("您可以放心使用银行流水解析器。")
        print_info("\n查看详细文档: README_PARSER.md")
    else:
        print_error("验收测试失败！")
        print_info("请检查上述错误信息并重新测试。")

    return success


def main():
    """主函数"""
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        file_path = None

    try:
        success = run_acceptance_test(file_path)
        sys.exit(0 if success else 1)
    except Exception as e:
        print_error(f"测试过程中发生错误: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
