from typing import List
from backend.app.billing.tariff_models import TEIRateComponent, TEIRateSchedule

def get_default_october_2026_components() -> List[TEIRateComponent]:
    return [
        TEIRateComponent(
            component_id="gen_charge",
            name="Generation Charge",
            category="generation_transmission",
            rate_per_kwh=6.74890,
            vat_treatment="fixed_rate",
            vat_rate_per_kwh=0.71120,
            unit="₱/kWh",
            description="Cost of electricity TEI purchases from power suppliers."
        ),
        TEIRateComponent(
            component_id="daa_adjustment",
            name="DAA (GRAM & ICERA)",
            category="generation_transmission",
            rate_per_kwh=0.00000,
            vat_treatment="vatable",
            unit="₱/kWh",
            description="Approved deferred fuel and purchased power adjustments."
        ),
        TEIRateComponent(
            component_id="trans_charge",
            name="Transmission Delivery Charge",
            category="generation_transmission",
            rate_per_kwh=0.85240,
            vat_treatment="vatable",
            unit="₱/kWh",
            description="Cost of delivering power through the NGCP national grid."
        ),
        TEIRateComponent(
            component_id="ancillary_charge",
            name="Ancillary Service Charge",
            category="generation_transmission",
            rate_per_kwh=0.38420,
            vat_treatment="vatable",
            unit="₱/kWh",
            description="Grid frequency and voltage stability support services."
        ),
        TEIRateComponent(
            component_id="system_loss_charge",
            name="System Loss Charge",
            category="generation_transmission",
            rate_per_kwh=0.54120,
            vat_treatment="exempt",
            unit="₱/kWh",
            description="Technical and non-technical energy lost in distribution lines."
        ),
        TEIRateComponent(
            component_id="dist_charge",
            name="Distribution Network Charge",
            category="distribution",
            rate_per_kwh=1.45200,
            vat_treatment="vatable",
            unit="₱/kWh",
            description="Operating, building, and maintaining TEI local poles and transformers."
        ),
        TEIRateComponent(
            component_id="supply_kwh_charge",
            name="Supply Charge (Per kWh)",
            category="distribution",
            rate_per_kwh=0.48500,
            vat_treatment="vatable",
            unit="₱/kWh",
            description="Billing, customer care, and energy account services per kWh."
        ),
        TEIRateComponent(
            component_id="supply_fixed_charge",
            name="Supply Charge (Monthly Fixed)",
            category="distribution",
            fixed_monthly=16.73000,
            vat_treatment="vatable",
            unit="₱/cust/mo",
            description="Fixed monthly account management charge."
        ),
        TEIRateComponent(
            component_id="metering_kwh_charge",
            name="Metering Charge (Per kWh)",
            category="distribution",
            rate_per_kwh=0.34200,
            vat_treatment="vatable",
            unit="₱/kWh",
            description="Meter maintenance, testing, and periodic data logging per kWh."
        ),
        TEIRateComponent(
            component_id="metering_fixed_charge",
            name="Metering Charge (Monthly Fixed)",
            category="distribution",
            fixed_monthly=5.00000,
            vat_treatment="vatable",
            unit="₱/cust/mo",
            description="Fixed monthly meter device maintenance fee."
        ),
        TEIRateComponent(
            component_id="reg_reset_adj",
            name="Regulatory Reset Cost Adjustment",
            category="other",
            rate_per_kwh=0.00000,
            vat_treatment="vatable",
            unit="₱/kWh",
            description="ERC regulatory reset rate adjustments."
        ),
        TEIRateComponent(
            component_id="missionary_electrification",
            name="Universal Charge - Missionary Electrification",
            category="other",
            rate_per_kwh=0.19800,
            vat_treatment="exempt",
            unit="₱/kWh",
            description="Government charge funding electricity to remote unserved off-grid islands."
        ),
        TEIRateComponent(
            component_id="environmental_charge",
            name="Universal Charge - Environmental Charge",
            category="other",
            rate_per_kwh=0.00250,
            vat_treatment="exempt",
            unit="₱/kWh",
            description="Government fee for watershed rehabilitation and clean energy management."
        ),
        TEIRateComponent(
            component_id="fit_all",
            name="Feed-in Tariff Allowance (FIT-All)",
            category="other",
            rate_per_kwh=0.03640,
            vat_treatment="exempt",
            unit="₱/kWh",
            description="Uniform national subsidy supporting grid-connected renewable solar and wind."
        ),
        TEIRateComponent(
            component_id="gea_all",
            name="Green Energy Auction Allowance (GEA-All)",
            category="other",
            rate_per_kwh=0.00000,
            vat_treatment="exempt",
            unit="₱/kWh",
            description="Green energy auction program support allowance."
        ),
        TEIRateComponent(
            component_id="local_franchise_tax",
            name="Local Franchise Tax",
            category="taxes",
            rate_per_kwh=0.00750,
            vat_treatment="exempt",
            unit="% of Gross",
            description="Municipal franchise tax assessed on electrical distribution revenue."
        ),
        TEIRateComponent(
            component_id="real_property_tax",
            name="Real Property Tax (RPT)",
            category="taxes",
            rate_per_kwh=0.02150,
            vat_treatment="exempt",
            unit="₱/kWh",
            description="Pass-through local government tax assessed on utility infrastructure assets."
        )
    ]

def get_default_october_2026_schedule() -> TEIRateSchedule:
    return TEIRateSchedule(
        id="tei-rate-2026-10-residential",
        effective_month="2026-10",
        customer_class="Residential",
        publication_date="2026-10-05",
        source_url="https://tarlacelectric.com/rate-schedule-customer-class",
        document_hash="tei_rate_oct_2026_verified_sha256",
        verification_status="verified",
        components=get_default_october_2026_components(),
        created_at="2026-10-05T08:00:00+08:00"
    )
