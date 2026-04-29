#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""分析PDF原始文本结构，优化正则表达式"""

import pdfplumber

def analyze_pdf_structure():
    file_path = 'assets/fa72fa84489945c5ac6bbba086307244.pdf.pdf'

    with pdfplumber.open(file_path) as pdf:
        # 提取所有文本
        all_text = ""
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                all_text += text + "\n"

        # 找到表头行
        lines = all_text.split('\n')
        header_idx = None
        header_line = None

        for i, line in enumerate(lines):
            if '交易日期' in line and '收入金额' in line:
                header_idx = i
                header_line = line
                break

        print("=== 表头行 ===")
        print(f"行号: {header_idx}")
        print(f"内容: {header_line}")
        print(f"长度: {len(header_line)}")

        # 显示前20行数据
        print("\n=== 前20行数据 ===")
        for i in range(header_idx + 1, min(header_idx + 21, len(lines))):
            line = lines[i].strip()
            if line and len(line) > 10:
                print(f"{i}: {repr(line)}")

        # 分析数据行的模式
        print("\n=== 数据行模式分析 ===")
        data_lines = []
        for i in range(header_idx + 1, len(lines)):
            line = lines[i].strip()
            if line and len(line) > 10:
                # 检查是否以日期开头
                if line[:8].isdigit():
                    data_lines.append(line)
                    if len(data_lines) >= 10:
                        break

        for i, line in enumerate(data_lines[:5]):
            print(f"\n行{i}:")
            print(f"  原始: {repr(line)}")
            print(f"  长度: {len(line)}")

            # 尝试不同的分割方式
            parts = line.split()
            print(f"  split(): {len(parts)} parts -> {parts[:10]}")

            parts_whitespace = line.split('  ')
            print(f"  split('  '): {len(parts_whitespace)} parts -> {parts_whitespace[:5]}")

if __name__ == '__main__':
    analyze_pdf_structure()
