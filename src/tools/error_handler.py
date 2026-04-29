"""
错误处理工具
提供详细的错误提示和恢复机制
"""
import traceback
from typing import Dict, Any, Optional
from datetime import datetime


class BankStatementError(Exception):
    """银行流水解析基础异常"""
    
    def to_dict(self) -> Dict[str, Any]:
        """将错误转换为字典格式"""
        return {
            "error_type": self.__class__.__name__,
            "message": str(self),
            "timestamp": datetime.now().isoformat(),
            "suggestion": "发生未知错误，请联系技术支持"
        }


class FileParseError(BankStatementError):
    """文件解析错误"""
    def __init__(self, message: str, file_path: str, details: Optional[str] = None):
        self.file_path = file_path
        self.details = details
        super().__init__(message)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_type": "FileParseError",
            "message": str(self),
            "file_path": self.file_path,
            "details": self.details,
            "timestamp": datetime.now().isoformat(),
            "suggestion": self._get_suggestion()
        }
    
    def _get_suggestion(self) -> str:
        if self.details and "不支持的文件类型" in self.details:
            return "请上传PDF、Excel、CSV或图片格式的银行流水文件"
        elif self.details and "PDF" in self.details:
            return "请检查PDF文件是否损坏或是否为扫描件，尝试重新上传"
        else:
            return "请检查文件格式是否正确，确保文件未损坏"


class ColumnMappingError(BankStatementError):
    """列名映射错误"""
    def __init__(self, message: str, headers: list, details: Optional[str] = None):
        self.headers = headers
        self.details = details
        super().__init__(message)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_type": "ColumnMappingError",
            "message": str(self),
            "headers": self.headers,
            "details": self.details,
            "timestamp": datetime.now().isoformat(),
            "suggestion": self._get_suggestion()
        }
    
    def _get_suggestion(self) -> str:
        if len(self.headers) == 0:
            return "无法识别表格列名，请检查文件中是否包含有效的表格数据"
        elif len(self.headers) < 3:
            return f"识别到的列数过少（{len(self.headers)}列），请确认文件中包含完整的交易明细表格"
        else:
            return f"识别到{len(self.headers)}列，但无法完全映射到标准字段，系统将使用LLM智能理解"


class DataCleaningError(BankStatementError):
    """数据清洗错误"""
    def __init__(self, message: str, row_index: int, row_data: list, details: Optional[str] = None):
        self.row_index = row_index
        self.row_data = row_data
        self.details = details
        super().__init__(message)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_type": "DataCleaningError",
            "message": str(self),
            "row_index": self.row_index,
            "row_data": self.row_data[:5] if len(self.row_data) > 5 else self.row_data,  # 只显示前5列
            "details": self.details,
            "timestamp": datetime.now().isoformat(),
            "suggestion": self._get_suggestion()
        }
    
    def _get_suggestion(self) -> str:
        if self.details and "金额" in self.details:
            return f"第{self.row_index + 1}行金额格式错误，系统已自动修复为0.00"
        elif self.details and "时间" in self.details:
            return f"第{self.row_index + 1}行时间格式错误，系统已自动修复为空字符串"
        else:
            return f"第{self.row_index + 1}行数据格式异常，系统已自动跳过该行"


class ValidationError(BankStatementError):
    """数据验证错误"""
    def __init__(self, message: str, validation_type: str, details: Optional[str] = None):
        self.validation_type = validation_type
        self.details = details
        super().__init__(message)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_type": "ValidationError",
            "message": str(self),
            "validation_type": self.validation_type,
            "details": self.details,
            "timestamp": datetime.now().isoformat(),
            "suggestion": self._get_suggestion()
        }
    
    def _get_suggestion(self) -> str:
        if self.validation_type == "balance_continuity":
            return "余额连续性验证失败，可能是数据不完整或计算错误"
        elif self.validation_type == "required_fields":
            return "必填字段验证失败，请检查交易时间、金额等关键字段是否完整"
        elif self.validation_type == "amount_balance":
            return "总金额平衡验证失败，请检查收入和支出金额的准确性"
        else:
            return "数据验证失败，请检查数据的完整性和准确性"


def format_error_response(error: Exception, include_traceback: bool = False) -> Dict[str, Any]:
    """
    格式化错误响应
    
    Args:
        error: 异常对象
        include_traceback: 是否包含堆栈信息
    
    Returns:
        格式化的错误字典
    """
    if isinstance(error, BankStatementError):
        error_dict = error.to_dict()
    else:
        error_dict = {
            "error_type": error.__class__.__name__,
            "message": str(error),
            "timestamp": datetime.now().isoformat(),
            "suggestion": "发生未知错误，请联系技术支持"
        }
    
    if include_traceback:
        error_dict["traceback"] = traceback.format_exc()
    
    return error_dict


def create_recovery_suggestion(error_dict: Dict[str, Any]) -> str:
    """
    创建恢复建议
    
    Args:
        error_dict: 错误字典
    
    Returns:
        恢复建议
    """
    error_type = error_dict.get("error_type", "UnknownError")
    
    if error_type == "FileParseError":
        return "建议：1) 检查文件格式是否正确；2) 尝试重新导出银行流水；3) 如果是扫描件，尝试使用高清扫描"
    elif error_type == "ColumnMappingError":
        return "建议：1) 检查表格列名是否清晰；2) 确保表格没有被合并单元格遮挡；3) 尝试使用Excel另存为CSV格式"
    elif error_type == "DataCleaningError":
        return "建议：1) 检查数据格式是否规范；2) 确保金额和时间字段没有特殊字符；3) 删除空行和无关数据"
    elif error_type == "ValidationError":
        return "建议：1) 检查数据的完整性；2) 确保余额计算正确；3) 验证必填字段是否都有值"
    else:
        return "建议：1) 重新上传文件；2) 检查文件大小是否超过限制；3) 联系技术支持获取帮助"


def log_error(error: Exception, context: Dict[str, Any]) -> str:
    """
    记录错误到日志
    
    Args:
        error: 异常对象
        context: 上下文信息
    
    Returns:
        日志字符串
    """
    error_type = error.__class__.__name__
    error_message = str(error)
    
    log_lines = [
        f"[ERROR] {datetime.now().isoformat()}",
        f"Error Type: {error_type}",
        f"Error Message: {error_message}",
        f"Context: {context}",
        "-" * 80
    ]
    
    if isinstance(error, BankStatementError):
        log_lines.append(f"Error Details: {error.to_dict()}")
    
    log_lines.append(traceback.format_exc())
    
    return "\n".join(log_lines)
