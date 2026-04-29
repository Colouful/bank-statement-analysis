# -*- coding: utf-8 -*-
"""文件解析工具 - 支持PDF、Excel、CSV、图片等多种格式"""

import os
import json
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
from langchain.tools import tool
from coze_coding_dev_sdk.fetch import FetchClient
from coze_coding_utils.runtime_ctx.context import Context, new_context
from pypdf import PdfReader


def _extract_text_from_fetch_response(response) -> Dict[str, Any]:
    """
    从FetchResponse中提取文本内容
    
    Args:
        response: FetchClient.fetch()返回的响应
        
    Returns:
        包含文本内容和元数据的字典
    """
    text_content = []
    images = []
    
    for item in response.content:
        if item.type == "text":
            text_content.append(item.text)
        elif item.type == "image":
            images.append({
                "url": item.image.display_url,
                "width": item.image.width,
                "height": item.image.height
            })
    
    return {
        "title": response.title,
        "text": "\n".join(text_content),
        "images": images,
        "status_code": response.status_code,
        "status_message": response.status_message,
        "url": response.url
    }


def _parse_local_pdf(file_path: str) -> Dict[str, Any]:
    """
    解析本地PDF文件
    
    Args:
        file_path: 本地文件路径
        
    Returns:
        包含解析结果的字典
    """
    try:
        # 读取PDF文件
        reader = PdfReader(file_path)
        
        # 提取所有文本
        text_lines = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                text_lines.extend(text.split("\n"))
        
        # 尝试识别表格结构
        headers = []
        rows = []
        
        for line in text_lines:
            line = line.strip()
            if not line:
                continue
            
            # 简单的表格识别逻辑（基于分隔符）
            if "|" in line:
                cells = [cell.strip() for cell in line.split("|") if cell.strip()]
                if not headers and len(cells) > 1:
                    headers = cells
                elif len(cells) > 1:
                    rows.append(cells)
            elif "\t" in line:
                cells = [cell.strip() for cell in line.split("\t") if cell.strip()]
                if not headers and len(cells) > 1:
                    headers = cells
                elif len(cells) > 1:
                    rows.append(cells)
        
        return {
            "success": True,
            "headers": headers,
            "rows": rows,
            "raw_text": "\n".join(text_lines),
            "metadata": {
                "file_path": file_path,
                "file_type": "pdf",
                "total_pages": len(reader.pages)
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"PDF解析失败: {str(e)}",
            "headers": [],
            "rows": []
        }


def _parse_pdf_or_image(file_url: str) -> Dict[str, Any]:
    """
    解析PDF或图片文件
    
    Args:
        file_url: 文件URL
        
    Returns:
        包含解析结果的字典
    """
    try:
        ctx = new_context(method="parse_file")
        client = FetchClient(ctx=ctx)
        response = client.fetch(url=file_url)
        
        result = _extract_text_from_fetch_response(response)
        
        # 提取表格数据
        text_lines = result["text"].split("\n")
        
        # 尝试识别表格结构
        headers = []
        rows = []
        current_row = []
        
        for line in text_lines:
            line = line.strip()
            if not line:
                continue
            
            # 简单的表格识别逻辑（基于分隔符）
            if "|" in line:
                cells = [cell.strip() for cell in line.split("|") if cell.strip()]
                if not headers and len(cells) > 1:
                    headers = cells
                elif len(cells) > 1:
                    rows.append(cells)
            elif "\t" in line:
                cells = [cell.strip() for cell in line.split("\t") if cell.strip()]
                if not headers and len(cells) > 1:
                    headers = cells
                elif len(cells) > 1:
                    rows.append(cells)
        
        return {
            "success": True,
            "headers": headers,
            "rows": rows,
            "raw_text": result["text"],
            "title": result["title"],
            "metadata": {
                "file_url": file_url,
                "file_type": "pdf/image",
                "images": result["images"]
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "headers": [],
            "rows": []
        }


def _parse_excel_or_csv(file_path: str) -> Dict[str, Any]:
    """
    解析Excel或CSV文件
    
    Args:
        file_path: 文件路径
        
    Returns:
        包含解析结果的字典
    """
    try:
        # 判断文件类型
        file_ext = os.path.splitext(file_path)[1].lower()
        
        if file_ext == ".csv":
            # 读取CSV文件
            df = pd.read_csv(file_path, encoding="utf-8-sig")
        elif file_ext in [".xlsx", ".xls"]:
            # 读取Excel文件
            df = pd.read_excel(file_path)
        else:
            return {
                "success": False,
                "error": f"不支持的文件类型: {file_ext}",
                "headers": [],
                "rows": []
            }
        
        # 提取表头
        headers = df.columns.tolist()
        
        # 提取数据行
        rows = []
        for _, row in df.iterrows():
            rows.append([str(cell) if pd.notna(cell) else "" for cell in row.values])
        
        return {
            "success": True,
            "headers": headers,
            "rows": rows,
            "metadata": {
                "file_path": file_path,
                "file_type": file_ext,
                "total_rows": len(rows),
                "total_columns": len(headers)
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "headers": [],
            "rows": []
        }


@tool
def parse_file(file_path_or_url: str) -> str:
    """
    解析银行流水文件（支持PDF、Excel、CSV、图片等格式）
    
    Args:
        file_path_or_url: 文件路径或URL
        
    Returns:
        JSON字符串，包含解析结果
    """
    # 判断是本地路径还是URL
    is_url = file_path_or_url.startswith("http://") or file_path_or_url.startswith("https://")
    
    # 检查文件扩展名
    file_ext = os.path.splitext(file_path_or_url)[1].lower()
    
    # 处理本地PDF文件
    if not is_url and file_ext == ".pdf":
        result = _parse_local_pdf(file_path_or_url)
    # 处理URL格式的PDF/图片文件
    elif is_url or file_ext in [".png", ".jpg", ".jpeg"]:
        result = _parse_pdf_or_image(file_path_or_url)
    else:
        # 本地Excel/CSV文件，使用Excel/CSV解析
        result = _parse_excel_or_csv(file_path_or_url)
    
    return json.dumps(result, ensure_ascii=False, indent=2)


@tool
def detect_bank_from_text(text: str) -> str:
    """
    从文本中识别银行名称
    
    Args:
        text: 文本内容
        
    Returns:
        银行名称（JSON格式）
    """
    from utils.constants import BANK_KEYWORDS
    
    detected_banks = []
    
    for bank_name, keywords in BANK_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text:
                if bank_name not in detected_banks:
                    detected_banks.append(bank_name)
                break
    
    result = {
        "detected_banks": detected_banks,
        "primary_bank": detected_banks[0] if detected_banks else None
    }
    
    return json.dumps(result, ensure_ascii=False, indent=2)


# 辅助函数：判断文件类型
def get_file_type(file_path_or_url: str) -> str:
    """
    判断文件类型
    
    Args:
        file_path_or_url: 文件路径或URL
        
    Returns:
        文件类型
    """
    if file_path_or_url.startswith("http://") or file_path_or_url.startswith("https://"):
        return "url"
    
    file_ext = os.path.splitext(file_path_or_url)[1].lower()
    
    if file_ext == ".pdf":
        return "pdf"
    elif file_ext in [".xlsx", ".xls"]:
        return "excel"
    elif file_ext == ".csv":
        return "csv"
    elif file_ext in [".jpg", ".jpeg", ".png", ".bmp"]:
        return "image"
    else:
        return "unknown"
