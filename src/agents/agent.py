# -*- coding: utf-8 -*-
"""银行流水解析 Agent 主逻辑"""

import os
import json
from typing import Annotated
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langgraph.graph import MessagesState
from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage
from coze_coding_utils.runtime_ctx.context import default_headers, new_context
from coze_coding_utils.log.write_log import request_context

from tools.file_parser import parse_file
from tools.column_mapper import map_columns
from tools.data_cleaner import clean_transaction_data
from tools.metadata_extractor import extract_metadata, extract_metadata_with_llm
from tools.data_validator import validate_transaction_data, validate_json_format
from tools.bank_learner import save_bank_mapping, get_learning_history

LLM_CONFIG = "config/agent_llm_config.json"

# 默认保留最近 20 轮对话 (40 条消息)
MAX_MESSAGES = 40

def _windowed_messages(old, new):
    """滑动窗口: 只保留最近 MAX_MESSAGES 条消息"""
    return add_messages(old, new)[-MAX_MESSAGES:] # type: ignore

class AgentState(MessagesState):
    messages: Annotated[list[AnyMessage], _windowed_messages]

def build_agent(ctx=None):
    """
    构建银行流水解析 Agent
    
    Returns:
        Agent 实例
    """
    workspace_path = os.getenv("COZE_WORKSPACE_PATH", "/workspace/projects")
    config_path = os.path.join(workspace_path, LLM_CONFIG)

    with open(config_path, 'r', encoding='utf-8') as f:
        cfg = json.load(f)

    api_key = os.getenv("COZE_WORKLOAD_IDENTITY_API_KEY")
    base_url = os.getenv("COZE_INTEGRATION_MODEL_BASE_URL")

    llm = ChatOpenAI(
        model=cfg['config'].get("model"),
        api_key=api_key,
        base_url=base_url,
        temperature=cfg['config'].get('temperature', 0.7),
        streaming=True,
        timeout=cfg['config'].get('timeout', 600),
        extra_body={
            "thinking": {
                "type": cfg['config'].get('thinking', 'disabled')
            }
        },
        default_headers=default_headers(ctx) if ctx else {}
    )

    # 定义可用的工具列表
    tools = [
        parse_file,                    # 解析文件内容
        map_columns,                   # 列名映射
        clean_transaction_data,        # 数据清洗
        extract_metadata,              # 提取元数据
        extract_metadata_with_llm,     # 使用LLM提取元数据
        validate_transaction_data,     # 数据验证
        validate_json_format,          # JSON格式验证
        save_bank_mapping,             # 保存新银行映射关系到规则文件
        get_learning_history           # 获取学习历史
    ]

    return create_agent(
        model=llm,
        system_prompt=cfg.get("sp"),
        tools=tools,
        checkpointer=None,  # 暂不使用记忆保存器
        state_schema=AgentState,
    )
