#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
创建测试数据集
生成各种格式的测试数据，用于边界测试
"""

import pandas as pd
import csv
import os

def create_test_csv():
    """创建CSV测试文件"""
    print("创建CSV测试文件...")

    # 标准银行流水数据
    data = [
        ["交易日期", "收入金额", "支出金额", "账户余额", "交易摘要", "对方账号", "对方户名"],
        ["2025-04-25", "", "370.00", "1184.30", "消费", "2088701741706645", "财付通"],
        ["2025-04-26", "", "45.00", "1139.30", "餐饮", "1234567890", "美团"],
        ["2025-04-27", "5000.00", "", "6139.30", "代发工资", "8111001012601041612", "成都公司"],
        ["2025-04-28", "", "128.00", "6011.30", "购物", "215500690", "京东"],
        ["2025-04-29", "", "35.00", "5976.30", "交通", "661511411", "滴滴"],
    ]

    csv_path = "test_data/bank_statement_test.csv"
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)

    with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(data)

    print(f"✅ CSV测试文件已创建: {csv_path}")
    return csv_path


def create_test_excel():
    """创建Excel测试文件"""
    print("创建Excel测试文件...")

    # 边界测试数据
    data = {
        "交易日期": [
            "2025-01-01",
            "2025-01-02",
            "2025-01-03",
            "2025-01-04",
            "2025-01-05",
            "",  # 边界：空日期
            "2025-01-07",
        ],
        "收入金额": [
            "",
            "",
            "10000.00",
            "",
            "500.50",
            "200.00",  # 边界：只有收入
            "",
        ],
        "支出金额": [
            "99.99",
            "0.01",
            "",
            "1234567.89",  # 边界：大金额
            "",
            "",
            "999999.99",  # 边界：接近最大值
        ],
        "账户余额": [
            "9001.00",
            "9000.99",
            "19000.99",
            "1775444.10",
            "1775444.60",
            "1775244.60",
            "775244.61",
        ],
        "交易摘要": [
            "测试消费1",
            "测试消费2",
            "工资收入",
            "大额转账",
            "小额收入",
            "边界测试",
            "大额支出",
        ],
        "对方账号": [
            "123456789",
            "",
            "8111001012601041612",
            "999999999999",
            "111111",
            "",
            "888888888888",
        ],
        "对方户名": [
            "测试商户A",
            "",  # 边界：空户名
            "测试公司",
            "大额商户",
            "个人",
            "",
            "未知商户",
        ],
    }

    df = pd.DataFrame(data)
    excel_path = "test_data/bank_statement_test.xlsx"
    os.makedirs(os.path.dirname(excel_path), exist_ok=True)

    df.to_excel(excel_path, index=False, engine='openpyxl')

    print(f"✅ Excel测试文件已创建: {excel_path}")
    return excel_path


def create_test_pdf_notes():
    """创建PDF测试说明文档"""
    print("创建PDF测试说明...")

    notes = """
银行流水解析器 - 测试说明

一、测试文件说明

1. PDF文件（中信银行）
   - 文件: assets/fa72fa84489945c5ac6bbba086307244.pdf.pdf
   - 数据量: 480笔交易
   - 特点: 包含收入/支出两列，格式标准

2. CSV测试文件
   - 文件: test_data/bank_statement_test.csv
   - 数据量: 5笔交易
   - 特点: 标准CSV格式，包含边界情况

3. Excel测试文件
   - 文件: test_data/bank_statement_test.xlsx
   - 数据量: 7笔交易
   - 特点: 包含各种边界情况（空值、大金额、只有收入等）

二、边界测试用例

1. 日期边界
   - 空日期
   - 格式不正确
   - 未来日期

2. 金额边界
   - 空金额
   - 0.01（最小金额）
   - 999999.99（接近最大值）
   - 只有收入
   - 只有支出
   - 大金额（1234567.89）

3. 文本边界
   - 空值
   - 特殊字符
   - 超长文本
   - 包含表情符号

4. 数据完整性
   - 缺少必填字段
   - 字段顺序错乱
   - 额外字段

三、测试步骤

1. 单格式测试
   - 测试PDF解析
   - 测试CSV解析
   - 测试Excel解析

2. 边界测试
   - 测试空值处理
   - 测试大金额处理
   - 测试异常格式

3. 性能测试
   - 测试大文件处理（>1000行）
   - 测试处理速度（< 5秒）

4. 准确性测试
   - 验证金额提取准确性
   - 验证日期格式转换
   - 验证交易类型推断

四、验收标准

✅ 所有格式都能成功解析
✅ 边界情况都能正确处理
✅ 金额提取准确率 100%
✅ 处理速度 < 5秒
✅ 无内存泄漏
✅ 错误提示清晰
"""

    notes_path = "test_data/测试说明.txt"
    os.makedirs(os.path.dirname(notes_path), exist_ok=True)

    with open(notes_path, 'w', encoding='utf-8') as f:
        f.write(notes)

    print(f"✅ 测试说明已创建: {notes_path}")


def main():
    """创建所有测试数据"""
    print("=" * 60)
    print("创建测试数据集")
    print("=" * 60)

    create_test_csv()
    create_test_excel()
    create_test_pdf_notes()

    print("\n" + "=" * 60)
    print("✅ 测试数据集创建完成！")
    print("=" * 60)

    print("\n测试文件列表:")
    print("  1. test_data/bank_statement_test.csv")
    print("  2. test_data/bank_statement_test.xlsx")
    print("  3. test_data/测试说明.txt")
    print("  4. assets/fa72fa84489945c5ac6bbba086307244.pdf.pdf（现有）")


if __name__ == '__main__':
    main()
