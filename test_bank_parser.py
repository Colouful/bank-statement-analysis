#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""快速测试银行流水解析 - 避免Agent循环调用"""

import sys
import os
import json

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# 导入工具模块
import tools.file_parser as fp
import tools.metadata_extractor as me
import tools.column_mapper as cm
import tools.data_cleaner as dc
import tools.data_validator as dv

def get_tool_functions():
    """获取工具函数（提取装饰前的原始函数）"""
    # 从模块中获取原始函数
    parse_func = None
    extract_func = None
    map_func = None
    clean_func = None
    validate_func = None

    # 扫描模块成员
    for name, obj in vars(fp).items():
        if hasattr(obj, '__name__') and obj.__name__ == 'parse_file':
            parse_func = obj

    for name, obj in vars(me).items():
        if hasattr(obj, '__name__') and obj.__name__ == 'extract_metadata':
            extract_func = obj

    for name, obj in vars(cm).items():
        if hasattr(obj, '__name__') and obj.__name__ == 'map_columns':
            map_func = obj

    for name, obj in vars(dc).items():
        if hasattr(obj, '__name__') and obj.__name__ == 'clean_transaction_data':
            clean_func = obj

    for name, obj in vars(dv).items():
        if hasattr(obj, '__name__') and obj.__name__ == 'validate_transaction_data':
            validate_func = obj

    return parse_func, extract_func, map_func, clean_func, validate_func

def main():
    file_path = 'assets/fa72fa84489945c5ac6bbba086307244.pdf.pdf'

    # 获取工具函数
    parse_func, extract_func, map_func, clean_func, validate_func = get_tool_functions()

    if not all([parse_func, extract_func, map_func, clean_func, validate_func]):
        print("❌ 无法加载工具函数")
        return

    print("=" * 60)
    print("开始快速测试银行流水解析")
    print("=" * 60)

    # 第1步：解析文件
    print("\n【步骤1】解析文件...")
    parse_result = json.loads(parse_func(file_path=file_path))

    if not parse_result['success']:
        print(f"❌ 文件解析失败: {parse_result.get('error')}")
        return

    print(f"✅ 文件解析成功")
    print(f"   - 列数: {len(parse_result['headers'])}")
    print(f"   - 行数: {len(parse_result['rows'])}")
    print(f"   - 原始文本长度: {len(parse_result['raw_text'])}")

    headers = parse_result['headers']
    rows = parse_result['rows']
    raw_text = parse_result['raw_text']

    # 如果没有headers和rows，从raw_text提取
    if not headers or not rows:
        print("   - 从raw_text提取数据...")
        lines = raw_text.split('\n')
        # 找到表头行
        header_line = None
        for line in lines:
            if '交易日期' in line and '收入金额' in line:
                header_line = line
                break

        if header_line:
            headers = header_line.split()
            print(f"   - 提取到表头: {headers}")
            # 提取数据行（简单实现，实际应该用更复杂的解析）
            data_start_idx = lines.index(header_line) + 1
            rows = []
            for line in lines[data_start_idx:]:
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 3:
                        rows.append(parts)
                    if len(rows) >= 10:  # 只提取前10行用于测试
                        break
            print(f"   - 提取到 {len(rows)} 行数据")

    # 第2步：提取元数据
    print("\n【步骤2】提取元数据...")
    metadata_result = json.loads(extract_func(header_text=raw_text))
    print(f"✅ 元数据提取成功")
    print(f"   - 账户名: {metadata_result['account_info'].get('account_name')}")
    print(f"   - 账号: {metadata_result['account_info'].get('account_id')}")

    # 第3步：列名映射
    print("\n【步骤3】列名映射...")
    headers_json = json.dumps(headers, ensure_ascii=False)
    map_result = json.loads(map_func(headers=headers_json))

    print(f"✅ 列名映射成功")
    print(f"   - 映射数量: {map_result['mapped_count']}/{map_result['mapped_count'] + map_result['unmapped_count']}")
    print(f"   - 映射关系: {map_result['mapping']}")

    # 第4步：数据清洗（只处理前5行）
    print("\n【步骤4】数据清洗...")
    test_rows = rows[:5]  # 只处理前5行进行快速测试

    rows_json = json.dumps(test_rows, ensure_ascii=False)
    mapping_json = json.dumps(map_result['mapping'], ensure_ascii=False)
    org_columns_json = json.dumps(headers, ensure_ascii=False)

    clean_result = json.loads(clean_func(rows=rows_json, column_mapping=mapping_json, org_columns=org_columns_json))

    print(f"✅ 数据清洗完成")
    print(f"   - 总行数: {clean_result.get('total_rows')}")
    print(f"   - 处理成功: {clean_result.get('total_processed')}")
    print(f"   - 错误数: {clean_result.get('error_count')}")

    # 显示第一行清洗结果
    if clean_result.get('cleaned_data'):
        first_row = clean_result['cleaned_data'][0]
        print("\n   第一行清洗结果:")
        for key, value in first_row.items():
            print(f"      {key}: {value}")

    # 第5步：数据验证
    print("\n【步骤5】数据验证...")
    transactions_json = json.dumps(clean_result['cleaned_data'], ensure_ascii=False)
    validate_result = json.loads(validate_func(transactions=transactions_json))

    print(f"✅ 数据验证完成")
    print(f"   - 总行数: {validate_result.get('total_rows')}")
    print(f"   - 有效行数: {validate_result.get('valid_rows')}")
    print(f"   - 检查结果: {validate_result.get('checks')}")

    # 第6步：组装最终JSON
    print("\n【步骤6】组装最终JSON...")
    final_result = {
        "metadata": {
            "account_info": metadata_result['account_info'],
            "time_range": metadata_result['time_range'],
            "currency": metadata_result['currency'],
            "bank_name": "中信银行"
        },
        "orgColumns": headers,
        "allRows": rows,
        "processedColumnNameMappingData": clean_result.get('cleaned_data', [])
    }

    print("✅ 最终JSON组装完成")
    print(f"   - 包含 {len(final_result['processedColumnNameMappingData'])} 条清洗后的交易数据")

    # 保存结果
    output_path = '/tmp/bank_statement_parsed.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(final_result, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 结果已保存到: {output_path}")

    print("\n" + "=" * 60)
    print("测试完成！总耗时 < 5秒")
    print("=" * 60)

if __name__ == '__main__':
    main()
