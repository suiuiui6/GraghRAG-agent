"""Pure stdlib public errors. Causes are internal and NOT traceback-redacted."""
MESSAGES = {'compatibility_not_approved':'兼容准入尚未批准','migration_required':'旧向量库需要显式迁移','runtime_unsupported':'SQLite 运行库不满足安全要求','runtime_hardening_failed':'SQLite 连接硬化失败','schema_mismatch':'向量库结构不符合规范','dimension_conflict':'向量维度与库清单冲突','model_conflict':'嵌入模型与库清单冲突','invalid_filter':'过滤条件无效','invalid_dimension':'向量维度无效','invalid_input':'输入记录或向量无效','unsupported_capability':'当前静态代不支持此操作','storage_unavailable':'向量存储暂不可用'}
OPERATIONS = {'open','compile','encode','search','read','count','scan'}
class VectorStoreError(Exception):
    def __init__(self, code, operation, *, length_mismatch=False):
        if code not in MESSAGES or operation not in OPERATIONS: raise ValueError('invalid internal error identity')
        self.code, self.operation, self.retryable = code, operation, False
        self.message = 'Length mismatch: 批次数量不一致' if length_mismatch else MESSAGES[code]
        super().__init__(self.message)
    def public_dict(self): return dict(code=self.code,operation=self.operation,retryable=self.retryable,message=self.message)
class VectorInputError(VectorStoreError, ValueError): pass
class VectorStorageError(VectorStoreError): pass
class VectorCapabilityError(VectorStoreError, ValueError): pass

