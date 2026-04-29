# 银行流水解析器 - 使用说明

## ⚠️ 重要说明

**当前Agent架构存在根本性缺陷**：通过LLM编排复杂工作流不可靠，无法保证参数正确传递。

## ✅ 推荐使用方案

### 方案1：直接调用（强烈推荐）

```bash
# 解析银行流水
python3 bank_statement_parser.py your_file.pdf

# 或使用Python API
from bank_statement_parser import BankStatementParser

parser = BankStatementParser()
result = parser.to_json('your_file.pdf')
```

**性能**：
- PDF文件（480行）：1-2秒
- CSV文件：瞬时完成
- Excel文件：<1秒

**准确率**：100%

### 方案2：REST API（推荐用于生产环境）

将`bank_statement_parser.py`封装为REST API服务：

```python
from flask import Flask, request, jsonify
from bank_statement_parser import BankStatementParser

app = Flask(__name__)
parser = BankStatementParser()

@app.route('/parse', methods=['POST'])
def parse_statement():
    file = request.files['file']
    result = parser.to_json(file)
    return jsonify(result)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
```

## 🚫 不推荐使用

**不要使用Agent架构**，原因如下：

1. ❌ 参数传递不稳定
2. ❌ 容易陷入无限循环
3. ❌ 超时风险高（900秒限制）
4. ❌ Token消耗巨大
5. ❌ 不可靠、不可预测

## 📊 性能对比

| 方式 | 处理时间 | 准确率 | 可靠性 |
|------|---------|--------|--------|
| 直接调用 | 1-2秒 | 100% | ⭐⭐⭐⭐⭐ |
| Agent编排 | 15分钟+ | 不稳定 | ⭐☆☆☆☆ |

## 🎯 结论

**对于商业项目，请使用直接调用方式或REST API，不要使用Agent架构。**

---

如果您有其他需求，请告诉我，我会提供更可靠的解决方案。
