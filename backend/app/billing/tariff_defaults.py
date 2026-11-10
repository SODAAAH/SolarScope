import datetime
from typing import List
from backend.app.billing.tariff_models import TEIRateComponent, TEIRateSchedule

def get_default_tei_components() -> List[TEIRateComponent]:
    return [
        TEIRateComponent(
            component_id="gen_charge",
            name="Generation Charge",
            category="generation_transmission",
            rate_per_kwh=0.0,
            vat_treatment="fixed_rate",
            vat_rate_per_kwh=0.0,
            unit="₱/kWh",
            description="Cost of electricity TEI purchases from power suppliers."
        ),
        TEIRateComponent(
            component_id="daa_adjustment",
            name="DAA (GRAM & ICERA)",
            category="generation_transmission",
            rate_per_kwh=0.0,
            vat_treatment="vatable",
            unit="₱/kWh",
            description="Approved deferred fuel and purchased power adjustments."
        ),
        TEIRateComponent(
            component_id="trans_charge",
            name="Transmission Delivery Charge",
            category="generation_transmission",
            rate_per_kwh=0.0,
            vat_treatment="vatable",
            unit="₱/kWh",
            description="Cost of delivering power through the NGCP national grid."
        ),
        TEIRateComponent(
            component_id="ancillary_charge",
            name="Ancillary Service Charge",
            category="generation_transmission",
            rate_per_kwh=0.0,
            vat_treatment="vatable",
            unit="₱/kWh",
            description="Grid frequency and voltage stability support services."
        ),
        TEIRateComponent(
            component_id="system_loss_charge",
            name="System Loss Charge",
            category="generation_transmission",
            rate_per_kwh=0.0,
            vat_treatment="exempt",
            unit="₱/kWh",
            description="Technical and non-technical energy lost in distribution lines."
        ),
        TEIRateComponent(
            component_id="dist_charge",
            name="Distribution Network Charge",
            category="distribution",
            rate_per_kwh=0.0,
            vat_treatment="vatable",
            unit="₱/kWh",
            description="Operating, building, and maintaining TEI local poles and transformers."
        ),
        TEIRateComponent(
            component_id="supply_kwh_charge",
            name="Supply Charge (Per kWh)",
            category="distribution",
            rate_per_kwh=0.0,
            vat_treatment="vatable",
            unit="₱/kWh",
            description="Billing, customer care, and energy account services per kWh."
        ),
        TEIRateComponent(
            component_id="supply_fixed_charge",
            name="Supply Charge (Monthly Fixed)",
            category="distribution",
            fixed_monthly=0.0,
            vat_treatment="vatable",
            unit="₱/cust/mo",
            description="Fixed monthly account management charge."
        ),
        TEIRateComponent(
            component_id="metering_kwh_charge",
            name="Metering Charge (Per kWh)",
            category="distribution",
            rate_per_kwh=0.0,
            vat_treatment="vatable",
            unit="₱/kWh",
            description="Meter maintenance, testing, and periodic data logging per kWh."
        ),
        TEIRateComponent(
            component_id="metering_fixed_charge",
            name="Metering Charge (Monthly Fixed)",
            category="distribution",
            fixed_monthly=0.0,
            vat_treatment="vatable",
            unit="₱/cust/mo",
            description="Fixed monthly meter device maintenance fee."
        ),
        TEIRateComponent(
            component_id="reg_reset_adj",
            name="Regulatory Reset Cost Adjustment",
            category="other",
            rate_per_kwh=0.0,
            vat_treatment="vatable",
            unit="₱/kWh",
            description="ERC regulatory reset rate adjustments."
        ),
        TEIRateComponent(
            component_id="missionary_electrification",
            name="Universal Charge - Missionary Electrification",
            category="other",
            rate_per_kwh=0.0,
            vat_treatment="exempt",
            unit="₱/kWh",
            description="Government charge funding electricity to remote unserved off-grid islands."
        ),
        TEIRateComponent(
            component_id="environmental_charge",
            name="Universal Charge - Environmental Charge",
            category="other",
            rate_per_kwh=0.0,
            vat_treatment="exempt",
            unit="₱/kWh",
            description="Government fee for watershed rehabilitation and clean energy management."
        ),
        TEIRateComponent(
            component_id="fit_all",
            name="Feed-in Tariff Allowance (FIT-All)",
            category="other",
            rate_per_kwh=0.0,
            vat_treatment="exempt",
            unit="₱/kWh",
            description="Uniform national subsidy supporting grid-connected renewable solar and wind."
        ),
        TEIRateComponent(
            component_id="gea_all",
            name="Green Energy Auction Allowance (GEA-All)",
            category="other",
            rate_per_kwh=0.0,
            vat_treatment="exempt",
            unit="₱/kWh",
            description="Green energy auction program support allowance."
        ),
        TEIRateComponent(
            component_id="local_franchise_tax",
            name="Local Franchise Tax",
            category="taxes",
            rate_per_kwh=0.0,
            vat_treatment="exempt",
            unit="% of Gross",
            description="Municipal franchise tax assessed on electrical distribution revenue."
        ),
        TEIRateComponent(
            component_id="real_property_tax",
            name="Real Property Tax (RPT)",
            category="taxes",
            rate_per_kwh=0.0,
            vat_treatment="exempt",
            unit="₱/kWh",
            description="Pass-through local government tax assessed on utility infrastructure assets."
        )
    ]

def get_default_tei_schedule() -> TEIRateSchedule:
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
    effective_month = now.strftime("%Y-%m")
    return TEIRateSchedule(
        id=f"tei-rate-{effective_month}-residential-unconfigured",
        effective_month=effective_month,
        customer_class="Residential",
        publication_date="",
        source_url="https://tarlacelectric.com/rate-schedule-customer-class",
        document_hash="",
        verification_status="unconfigured",
        components=get_default_tei_components(),
        created_at=now.isoformat()
    )
