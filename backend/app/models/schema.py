import enum
from sqlalchemy import Column, String, Integer, Date, Enum, ForeignKey, Text
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


class ReportAccessEnum(str, enum.Enum):
    paid = "paid"
    public = "public"


class Report(Base):
    """
    Existing reports table in project_atlas database.
    Stores intelligence and market research reports.
    """
    __tablename__ = "reports"

    id = Column(String(10), primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    publisher = Column(String(100), nullable=False)
    published = Column(Date, nullable=False)
    sector = Column(String(50), nullable=False)
    access = Column(Enum("paid", "public", name="report_access_enum"), nullable=False)

    # Relationship to market metrics
    metrics = relationship("MarketMetric", back_populates="report", cascade="all")

    def __repr__(self):
        return f"<Report(id='{self.id}', title='{self.title}', publisher='{self.publisher}')>"


class MarketMetric(Base):
    """
    Existing market_metrics table in project_atlas database.
    Stores granular analytical indicators, CAGR, regional shares, and values extracted from reports.
    """
    __tablename__ = "market_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    report_id = Column(String(10), ForeignKey("reports.id"), nullable=True, index=True)
    metric = Column(String(100), nullable=True)
    region = Column(String(100), nullable=True)
    period = Column(String(50), nullable=True)
    value = Column(String(50), nullable=True)
    scope_note = Column(Text, nullable=True)

    # Relationship back to report
    report = relationship("Report", back_populates="metrics")

    def __repr__(self):
        return f"<MarketMetric(id={self.id}, report_id='{self.report_id}', metric='{self.metric}', value='{self.value}')>"


class Client(Base):
    """
    Existing clients table in project_atlas database.
    Stores enterprise client contact information and purchased report access IDs.
    """
    __tablename__ = "clients"

    id = Column(String(10), primary_key=True, index=True)
    company = Column(String(100), nullable=False)
    contact_email = Column(String(100), nullable=False)
    purchased_reports = Column(Text, nullable=False)

    def __repr__(self):
        return f"<Client(id='{self.id}', company='{self.company}', email='{self.contact_email}')>"
