# 数据库日志模块 - 记录每次 API 调用的模型、输入、输出、Token 用量和耗时
import asyncio
import json
from datetime import UTC, datetime
from functools import lru_cache

from sqlalchemy import Column, DateTime, Float, Integer, String, Text, create_engine
from sqlalchemy.orm import Session, declarative_base

from backend.config import DATABASE_PATH

Base = declarative_base()


class CallLog(Base):
    """API 调用日志记录表"""

    __tablename__ = "call_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(
        DateTime,
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
        nullable=False,
    )
    provider = Column(String(50), nullable=False)  # 供应商: deepseek / dashscope
    model = Column(String(100), nullable=False)  # 模型名称
    call_type = Column(String(50), nullable=False)  # 调用类型
    input_data = Column(Text, nullable=True)  # 输入（JSON）
    output_data = Column(Text, nullable=True)  # 输出（JSON）
    prompt_tokens = Column(Integer, default=0)  # 输入 Token 数
    completion_tokens = Column(Integer, default=0)  # 输出 Token 数
    total_tokens = Column(Integer, default=0)  # 总 Token 数
    elapsed_ms = Column(Float, default=0.0)  # 耗时（毫秒）
    error = Column(Text, nullable=True)  # 错误信息


@lru_cache(maxsize=1)
def get_engine():
    """获取数据库引擎（全局单例，仅首次创建表）"""
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{DATABASE_PATH}")
    Base.metadata.create_all(engine)
    return engine


def _log_to_dict(log):
    """将 ORM 对象转换为字典"""
    return {
        "id": log.id,
        "timestamp": log.timestamp.isoformat(),
        "provider": log.provider,
        "model": log.model,
        "call_type": log.call_type,
        "input_data": json.loads(log.input_data) if log.input_data else None,
        "output_data": json.loads(log.output_data) if log.output_data else None,
        "prompt_tokens": log.prompt_tokens,
        "completion_tokens": log.completion_tokens,
        "total_tokens": log.total_tokens,
        "elapsed_ms": log.elapsed_ms,
        "error": log.error,
    }


SECRET_KEYS = {"api_key", "_api_key", "authorization", "x-api-key"}


def redact_secrets(data):
    """递归移除历史记录中的密钥字段"""
    if isinstance(data, dict):
        return {
            key: ("***" if key in SECRET_KEYS else redact_secrets(value))
            for key, value in data.items()
        }
    if isinstance(data, list):
        return [redact_secrets(item) for item in data]
    return data


def save_call_log(
    provider,
    model,
    call_type,
    input_data,
    output_data,
    prompt_tokens=0,
    completion_tokens=0,
    total_tokens=0,
    elapsed_ms=0.0,
    error=None,
):
    """保存一条 API 调用日志"""
    engine = get_engine()
    with Session(engine) as session:
        log = CallLog(
            provider=provider,
            model=model,
            call_type=call_type,
            input_data=json.dumps(redact_secrets(input_data), ensure_ascii=False) if input_data else None,
            output_data=json.dumps(redact_secrets(output_data), ensure_ascii=False) if output_data else None,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            elapsed_ms=elapsed_ms,
            error=error,
        )
        session.add(log)
        session.commit()
        return log.id


def get_call_history(limit=50):
    """获取最近的调用历史"""
    engine = get_engine()
    with Session(engine) as session:
        logs = session.query(CallLog).order_by(CallLog.timestamp.desc()).limit(limit).all()
        return [_log_to_dict(log) for log in logs]


def get_call_log(log_id):
    """获取单条调用历史"""
    engine = get_engine()
    with Session(engine) as session:
        log = session.get(CallLog, log_id)
        return _log_to_dict(log) if log else None


async def save_call_log_async(*args, **kwargs):
    """异步保存日志，避免阻塞事件循环"""
    return await asyncio.to_thread(save_call_log, *args, **kwargs)


async def get_call_history_async(limit=50):
    """异步获取调用历史"""
    return await asyncio.to_thread(get_call_history, limit)


async def get_call_log_async(log_id):
    """异步获取单条调用历史"""
    return await asyncio.to_thread(get_call_log, log_id)
