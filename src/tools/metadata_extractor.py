# -*- coding: utf-8 -*-
"""元数据提取工具 - 从文件头部提取账户信息等元数据"""

import json
import re
from typing import Dict, List, Any, Optional
from datetime import datetime
from langchain.tools import tool
from coze_coding_dev_sdk import LLMClient
from coze_coding_utils.runtime_ctx.context import new_context
from langchain_core.messages import SystemMessage, HumanMessage

from utils.constants import BANK_KEYWORDS


def _extract_account_info(text: str) -> Dict[str, Any]:
    """提取账户信息"""
    account_info = {
        "account_id": "",
        "account_name": "",
        "account_type": "bank_account",
        "idcard": ""
    }
    
    # 提取账号
    account_patterns = [
        r"账号[：:]\s*(\d{10,25})",
        r"卡号[：:]\s*(\d{10,25})",
        r"卡/账号[：:]\s*(\d{10,25})",
        r"账户[：:]\s*(\d{10,25})"
    ]
    
    for pattern in account_patterns:
        match = re.search(pattern, text)
        if match:
            account_info["account_id"] = match.group(1)
            break
    
    # 提取户名
    name_patterns = [
        r"户名[：:]\s*([^\s\n]+)",
        r"客户姓名[：:]\s*([^\s\n]+)",
        r"姓名[：:]\s*([^\s\n]+)"
    ]
    
    for pattern in name_patterns:
        match = re.search(pattern, text)
        if match:
            account_info["account_name"] = match.group(1)
            break
    
    # 提取证件号
    idcard_patterns = [
        r"证件号码[：:]\s*([A-Z0-9]{15,20})",
        r"证件号[：:]\s*([A-Z0-9]{15,20})"
    ]
    
    for pattern in idcard_patterns:
        match = re.search(pattern, text)
        if match:
            account_info["idcard"] = match.group(1)
            break
    
    return account_info


def _extract_time_range(text: str) -> Dict[str, Any]:
    """提取时间范围"""
    time_range = {
        "start_time": "",
        "end_time": "",
        "display_text": ""
    }
    
    # 提取起始和结束日期
    date_patterns = [
        r"起始日期[：:]\s*(\d{4}[-/.年]\d{1,2}[-/.月]\d{1,2})",
        r"开始日期[：:]\s*(\d{4}[-/.年]\d{1,2}[-/.月]\d{1,2})",
        r"查询起日[：:]\s*(\d{4}[-/.年]\d{1,2}[-/.月]\d{1,2})"
    ]
    
    for pattern in date_patterns:
        match = re.search(pattern, text)
        if match:
            time_range["start_time"] = match.group(1)
            break
    
    date_patterns_end = [
        r"结束日期[：:]\s*(\d{4}[-/.年]\d{1,2}[-/.月]\d{1,2})",
        r"终止日期[：:]\s*(\d{4}[-/.年]\d{1,2}[-/.月]\d{1,2})",
        r"查询止日[：:]\s*(\d{4}[-/.年]\d{1,2}[-/.月]\d{1,2})"
    ]
    
    for pattern in date_patterns_end:
        match = re.search(pattern, text)
        if match:
            time_range["end_time"] = match.group(1)
            break
    
    # 提取起止日期范围
    range_pattern = r"起止日期[：:]\s*(\d{4}[-/.年]\d{1,2}[-/.月]\d{1,2})\s*[—-至到]\s*(\d{4}[-/.年]\d{1,2}[-/.月]\d{1,2})"
    match = re.search(range_pattern, text)
    if match:
        time_range["start_time"] = match.group(1)
        time_range["end_time"] = match.group(2)
    
    if time_range["start_time"] and time_range["end_time"]:
        time_range["display_text"] = f"{time_range['start_time']} 00:00:00 至 {time_range['end_time']} 23:59:59"
    
    return time_range


def _extract_currency(text: str) -> Dict[str, Any]:
    """提取币种信息"""
    currency = {
        "currency_code": "CNY",
        "currency_name": "人民币",
        "unit": "元"
    }
    
    # 提取币种
    currency_pattern = r"币种[：:]\s*([^\s\n]+)"
    match = re.search(currency_pattern, text)
    if match:
        currency_name = match.group(1)
        currency["currency_name"] = currency_name
        
        # 币种代码映射
        currency_code_map = {
            "人民币": "CNY",
            "美元": "USD",
            "港币": "HKD",
            "欧元": "EUR",
            "日元": "JPY"
        }
        currency["currency_code"] = currency_code_map.get(currency_name, "CNY")
    
    return currency


def _detect_bank(text: str) -> Optional[str]:
    """识别银行"""
    for bank_name, keywords in BANK_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text:
                return bank_name
    return None


def _extract_title(text: str) -> str:
    """提取文档标题"""
    # 通常标题在文件开头
    lines = text.split("\n")[:10]
    for line in lines:
        line = line.strip()
        if line and not line.startswith("账号") and not line.startswith("户名"):
            # 排除账号、户名等字段
            if len(line) > 5 and len(line) < 50:
                return line
    return "银行流水明细"


@tool
def extract_metadata(header_text: str) -> str:
    """
    从文件头部文本中提取元数据
    
    Args:
        header_text: 文件头部文本
        
    Returns:
        JSON字符串，包含元数据
    """
    try:
        # 提取各项信息
        account_info = _extract_account_info(header_text)
        time_range = _extract_time_range(header_text)
        currency = _extract_currency(header_text)
        bank_name = _detect_bank(header_text)
        title = _extract_title(header_text)
        
        # 构建原始元数据
        original_metadata = {}
        
        # 提取所有键值对
        kv_pattern = r"([^：:\n]+)[：:]\s*([^\n]+)"
        for match in re.finditer(kv_pattern, header_text):
            key = match.group(1).strip()
            value = match.group(2).strip()
            if key and value:
                original_metadata[key] = value
        
        # 构建完整元数据
        metadata = {
            "title": title,
            "document_type": bank_name.lower() if bank_name else "unknown",
            "document_id": account_info["account_id"],
            "document_category": "交易明细",
            "account_info": account_info,
            "currency": currency,
            "time_range": time_range,
            "extra": {
                "original_metadata": original_metadata,
                "bank_name": bank_name
            },
            "version": "v1"
        }
        
        return json.dumps(metadata, ensure_ascii=False, indent=2)
        
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@tool
def extract_metadata_with_llm(file_content: str) -> str:
    """
    使用LLM提取元数据（用于复杂情况）
    
    Args:
        file_content: 文件内容
        
    Returns:
        JSON字符串，包含元数据
    """
    system_prompt = """你是银行流水解析专家，擅长从银行流水文件中提取关键信息。

你的任务是从文件内容中提取以下元数据：
1. 账户信息（账号、户名、证件号等）
2. 时间范围（起始日期、结束日期）
3. 币种信息
4. 银行名称
5. 文档标题
6. 其他关键信息

输出格式（只返回JSON，不要其他说明）：
{
  "title": "文档标题",
  "document_type": "银行标识（如icbc, abc等）",
  "document_id": "账号",
  "document_category": "交易明细",
  "account_info": {
    "account_id": "账号",
    "account_name": "户名",
    "account_type": "bank_account",
    "idcard": "证件号"
  },
  "currency": {
    "currency_code": "CNY",
    "currency_name": "人民币",
    "unit": "元"
  },
  "time_range": {
    "start_time": "起始日期",
    "end_time": "结束日期",
    "display_text": "显示文本"
  },
  "extra": {
    "original_metadata": {
      "标题": "xxx",
      "客户姓名": "xxx",
      ...
    }
  },
  "version": "v1"
}"""

    human_message = f"""请从以下银行流水文件内容中提取元数据：

文件内容：
{file_content[:2000]}

请返回提取的元数据（JSON格式）。"""

    try:
        ctx = new_context(method="metadata_extraction")
        client = LLMClient(ctx=ctx)
        
        response = client.invoke(
            messages=[
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_message)
            ],
            model="doubao-seed-2-0-pro-260215",
            temperature=0.3,
            max_completion_tokens=4096
        )
        
        content = response.content
        if isinstance(content, str):
            content = content.strip()
        
        # 提取JSON
        if isinstance(content, str):
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
        
        return content
        
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)
