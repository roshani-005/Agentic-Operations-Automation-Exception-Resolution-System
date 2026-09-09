from datetime import datetime
import json

from sqlalchemy import Column, DateTime, Integer, String, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings


engine = create_engine(settings.database_url, connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True)
    order_id = Column(String, unique=True, index=True, nullable=False)
    customer_id = Column(String, nullable=False)
    amount = Column(Integer, nullable=False)
    status = Column(String, nullable=False)
    failure_reason = Column(String, nullable=True)


class TaskAudit(Base):
    __tablename__ = "task_audit"
    id = Column(Integer, primary_key=True)
    task_id = Column(String, index=True, nullable=False)
    status = Column(String, nullable=False)
    task = Column(Text, nullable=False)
    answer = Column(Text, nullable=True)
    retries = Column(Integer, default=0)
    audit_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        if db.query(Order).count() == 0:
            db.add_all([
                Order(order_id="ORD-1001", customer_id="CUST-1", amount=1299, status="completed"),
                Order(order_id="ORD-1002", customer_id="CUST-2", amount=8999, status="failed", failure_reason="payment_declined"),
                Order(order_id="ORD-1003", customer_id="CUST-3", amount=15999, status="failed", failure_reason="inventory_mismatch"),
            ])
            db.commit()


def persist_task(state) -> None:
    with SessionLocal() as db:
        row = TaskAudit(
            task_id=state.task_id,
            status=state.final_status,
            task=state.task,
            answer=state.final_answer,
            retries=state.retry_count,
            audit_json=json.dumps([event.model_dump(mode="json") for event in state.audit_log]),
        )
        db.add(row)
        db.commit()


def get_task(task_id: str):
    with SessionLocal() as db:
        return db.query(TaskAudit).filter(TaskAudit.task_id == task_id).order_by(TaskAudit.id.desc()).first()
