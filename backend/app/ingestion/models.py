from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class ColumnMappingItem(BaseModel):
    original_name: str
    canonical_name: Optional[str] = None
    unit: Optional[str] = None
    data_type: str = "numeric"
    confidence: float = 0.0
    sample_values: List[Any] = Field(default_factory=list)
    sign_convention: str = "positive"
    is_duplicate: bool = False
    duplicate_of: Optional[str] = None
    is_inactive: bool = False

class DatasetPreviewResponse(BaseModel):
    dataset_id: str
    filename: str
    available_sheets: List[str]
    selected_sheet: str
    total_rows: int
    columns: List[ColumnMappingItem]
    detected_start_time: Optional[str] = None
    detected_end_time: Optional[str] = None
    estimated_interval_minutes: Optional[float] = None
    preview_rows: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

class CommitMappingRequest(BaseModel):
    dataset_id: str
    selected_sheet: str
    mappings: Dict[str, str]
    sign_conventions: Dict[str, str] = Field(default_factory=dict)
    timezone: str = "Asia/Manila"

class CanonicalRecord(BaseModel):
    timestamp: str
    pv_power_kw: float = 0.0
    load_power_kw: float = 0.0
    grid_power_kw: float = 0.0
    battery_power_kw: float = 0.0
    soc_percent: float = 0.0
    generator_power_kw: float = 0.0
    grid_tied_inverter_power_kw: float = 0.0
    residual_power_kw: float = 0.0
    quality_flags: List[str] = Field(default_factory=list)
