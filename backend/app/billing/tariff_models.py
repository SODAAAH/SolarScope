from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class TEIRateComponent(BaseModel):
    component_id: str
    name: str
    category: str
    rate_per_kwh: float = 0.0
    rate_per_kw: float = 0.0
    fixed_monthly: float = 0.0
    vat_treatment: str = "vatable"
    vat_rate_per_kwh: float = 0.0
    unit: str = "₱/kWh"
    description: str = ""
    is_active: bool = True

class TEIRateSchedule(BaseModel):
    id: str
    effective_month: str
    customer_class: str = "Residential"
    publication_date: str
    source_url: str = "https://tarlacelectric.com/rate-schedule-customer-class"
    document_hash: str = ""
    verification_status: str = "verified"
    components: List[TEIRateComponent] = Field(default_factory=list)
    created_at: str

class TEIBillingProfile(BaseModel):
    customer_class: str = "Residential"
    billing_cycle_day: int = 18
    cycle_start_date: Optional[str] = None
    cycle_end_date: Optional[str] = None
    prev_meter_reading: Optional[float] = None
    latest_meter_reading: Optional[float] = None
    meter_reading_date: Optional[str] = None
    connection_type: str = "behind_meter"
    is_lifeline_eligible: bool = False
    is_senior_eligible: bool = False
    is_prompt_payment_eligible: bool = False
    previous_unpaid_balance: float = 0.0
    payments_received: float = 0.0
    forecast_method: str = "7day"
    updated_at: Optional[str] = None

class BillLineItem(BaseModel):
    component_id: str
    name: str
    category: str
    rate_applied: float
    rate_unit: str
    billed_quantity: float
    amount: float
    vat_amount: float
    total_with_vat: float
    explanation: str
    formula: str
    vat_treatment: str

class StatementOfAccount(BaseModel):
    billing_period_start: str
    billing_period_end: str
    customer_class: str
    effective_rate_schedule_month: str
    billed_kwh: float
    generation_transmission_charges: float
    distribution_charges: float
    other_charges: float
    subtotal_electricity_charges: float
    government_taxes: float
    discounts: float
    net_metering_credits: float
    total_current_charges: float
    previous_unpaid_balance: float
    payments_received: float
    total_amount_due: float
    line_items: List[BillLineItem] = Field(default_factory=list)
    effective_average_rate_per_kwh: float
    is_estimate: bool = True
    disclaimer: str = "SolarScope Bill Estimate — Not an Official TEI Statement of Account."

class BillForecastScenario(BaseModel):
    name: str
    description: str
    projected_additional_kwh: float
    total_projected_kwh: float
    estimated_current_charges: float
    estimated_total_amount: float
    daily_import_rate_kwh: float
    statement: StatementOfAccount

class BillForecastResponse(BaseModel):
    billing_cycle_start: str
    billing_cycle_end: str
    next_meter_reading_date: str
    days_elapsed: int
    days_remaining: int
    cycle_total_days: int
    actual_imported_kwh: float
    actual_exported_kwh: float
    active_rate_effective_month: str
    active_generation_charge: float
    active_generation_vat: float
    last_rate_check_timestamp: str
    rate_monitor_status: str
    rate_change_alert: Optional[Dict[str, Any]] = None
    current_so_far_statement: StatementOfAccount
    lower_estimate: BillForecastScenario
    expected_estimate: BillForecastScenario
    higher_estimate: BillForecastScenario
    forecasting_method: str
    data_coverage_percent: float
    solar_savings: Dict[str, Any]
