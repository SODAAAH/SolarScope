from typing import List, Dict, Any, Optional
from backend.app.billing.tariff_models import (
    TEIRateSchedule,
    TEIRateComponent,
    TEIBillingProfile,
    BillLineItem,
    StatementOfAccount
)

def calculate_statement_of_account(
    billed_kwh: float,
    schedule: TEIRateSchedule,
    profile: TEIBillingProfile,
    billing_start: str,
    billing_end: str,
    exported_kwh: float = 0.0,
    is_estimate: bool = True
) -> StatementOfAccount:
    billed_kwh = max(0.0, float(billed_kwh))
    exported_kwh = max(0.0, float(exported_kwh))

    line_items: List[BillLineItem] = []
    gen_trans_total = 0.0
    dist_total = 0.0
    other_total = 0.0
    vat_total = 0.0

    gen_rate = 0.0
    gen_vat_rate = 0.0
    for comp in schedule.components:
        if comp.component_id == "gen_charge":
            gen_rate = comp.rate_per_kwh
            gen_vat_rate = comp.vat_rate_per_kwh

    for comp in schedule.components:
        if comp.category not in ["generation_transmission", "distribution", "other"]:
            continue

        if comp.fixed_monthly > 0:
            qty = 1.0
            rate_applied = comp.fixed_monthly
            rate_unit = comp.unit
            amount = round(comp.fixed_monthly, 2)
            formula_str = f"Fixed monthly service charge: ₱{comp.fixed_monthly:.2f}"
        else:
            qty = billed_kwh
            rate_applied = comp.rate_per_kwh
            rate_unit = comp.unit
            amount = round(billed_kwh * comp.rate_per_kwh, 2)
            formula_str = f"{billed_kwh:.2f} kWh × ₱{comp.rate_per_kwh:.5f}/{comp.unit.replace('₱/', '')}"

        if comp.vat_treatment == "fixed_rate":
            vat_amt = round(billed_kwh * comp.vat_rate_per_kwh, 2)
        elif comp.vat_treatment == "vatable":
            vat_amt = round(amount * 0.12, 2)
        else:
            vat_amt = 0.0

        vat_total += vat_amt
        total_with_vat = round(amount + vat_amt, 2)

        if comp.category == "generation_transmission":
            gen_trans_total += amount
        elif comp.category == "distribution":
            dist_total += amount
        elif comp.category == "other":
            other_total += amount

        line_items.append(
            BillLineItem(
                component_id=comp.component_id,
                name=comp.name,
                category=comp.category,
                rate_applied=rate_applied,
                rate_unit=rate_unit,
                billed_quantity=qty,
                amount=amount,
                vat_amount=vat_amt,
                total_with_vat=total_with_vat,
                explanation=comp.description,
                formula=formula_str,
                vat_treatment=comp.vat_treatment
            )
        )

    subtotal_charges = round(gen_trans_total + dist_total + other_total, 2)

    rpt_component = next((c for c in schedule.components if c.component_id == "real_property_tax"), None)
    rpt_rate = rpt_component.rate_per_kwh if rpt_component else 0.0
    rpt_amount = round(billed_kwh * rpt_rate, 2)

    franchise_component = next((c for c in schedule.components if c.component_id == "local_franchise_tax"), None)
    franchise_rate = franchise_component.rate_per_kwh if franchise_component else 0.0
    franchise_amount = round(subtotal_charges * franchise_rate, 2)

    total_taxes = round(vat_total + rpt_amount + franchise_amount, 2)

    line_items.append(
        BillLineItem(
            component_id="local_franchise_tax",
            name="Local Franchise Tax",
            category="taxes",
            rate_applied=franchise_rate,
            rate_unit="% of Gross",
            billed_quantity=subtotal_charges,
            amount=franchise_amount,
            vat_amount=0.0,
            total_with_vat=franchise_amount,
            explanation="Local government tax on gross electric revenues.",
            formula=f"{franchise_rate * 100:.2f}% × ₱{subtotal_charges:.2f} Gross Electricity Charges",
            vat_treatment="exempt"
        )
    )

    line_items.append(
        BillLineItem(
            component_id="real_property_tax",
            name="Real Property Tax (RPT)",
            category="taxes",
            rate_applied=rpt_rate,
            rate_unit="₱/kWh",
            billed_quantity=billed_kwh,
            amount=rpt_amount,
            vat_amount=0.0,
            total_with_vat=rpt_amount,
            explanation="Pass-through tax assessed on utility infrastructure assets.",
            formula=f"{billed_kwh:.2f} kWh × ₱{rpt_rate:.5f}/kWh",
            vat_treatment="exempt"
        )
    )

    line_items.append(
        BillLineItem(
            component_id="vat_total_item",
            name="Value Added Tax (Line Item Total)",
            category="taxes",
            rate_applied=0.12,
            rate_unit="itemized",
            billed_quantity=billed_kwh,
            amount=vat_total,
            vat_amount=0.0,
            total_with_vat=vat_total,
            explanation="Government VAT calculated per eligible charge component.",
            formula=f"Itemized VAT (Generation fixed ₱{gen_vat_rate:.5f}/kWh + 12% on Transmission & Distribution)",
            vat_treatment="vatable"
        )
    )

    total_discounts = 0.0
    if profile.is_lifeline_eligible and billed_kwh <= 100.0:
        lifeline_pct = 0.0
        if billed_kwh <= 20.0:
            lifeline_pct = 1.00
        elif billed_kwh <= 50.0:
            lifeline_pct = 0.50
        elif billed_kwh <= 70.0:
            lifeline_pct = 0.35
        elif billed_kwh <= 100.0:
            lifeline_pct = 0.20

        if lifeline_pct > 0.0:
            discount_base = gen_trans_total + dist_total
            lifeline_discount = round(discount_base * lifeline_pct, 2)
            total_discounts += lifeline_discount
            line_items.append(
                BillLineItem(
                    component_id="lifeline_discount",
                    name=f"Lifeline Discount ({int(lifeline_pct * 100)}%)",
                    category="discounts",
                    rate_applied=lifeline_pct,
                    rate_unit="%",
                    billed_quantity=billed_kwh,
                    amount=-lifeline_discount,
                    vat_amount=0.0,
                    total_with_vat=-lifeline_discount,
                    explanation="Government assistance discount for qualified low-consumption households.",
                    formula=f"{int(lifeline_pct * 100)}% discount on Gen/Trans/Dist base (₱{discount_base:.2f})",
                    vat_treatment="exempt"
                )
            )

    if profile.is_senior_eligible and billed_kwh <= 100.0:
        senior_base = gen_trans_total + dist_total
        senior_discount = round(senior_base * 0.05, 2)
        total_discounts += senior_discount
        line_items.append(
            BillLineItem(
                component_id="senior_citizen_discount",
                name="Senior Citizen Discount (5%)",
                category="discounts",
                rate_applied=0.05,
                rate_unit="%",
                billed_quantity=billed_kwh,
                amount=-senior_discount,
                vat_amount=0.0,
                total_with_vat=-senior_discount,
                explanation="5% discount on generation, transmission, and distribution for registered senior citizens.",
                formula=f"5% × ₱{senior_base:.2f} qualified electricity charges",
                vat_treatment="exempt"
            )
        )

    if profile.is_prompt_payment_eligible:
        prompt_discount = round(dist_total * 0.01, 2)
        total_discounts += prompt_discount
        line_items.append(
            BillLineItem(
                component_id="prompt_payment_discount",
                name="Prompt Payment Discount (1%)",
                category="discounts",
                rate_applied=0.01,
                rate_unit="%",
                billed_quantity=dist_total,
                amount=-prompt_discount,
                vat_amount=0.0,
                total_with_vat=-prompt_discount,
                explanation="Incentive discount on distribution charge for payment within prompt window.",
                formula=f"1% × ₱{dist_total:.2f} distribution charges",
                vat_treatment="exempt"
            )
        )

    net_metering_credits = 0.0
    if profile.connection_type == "net_metering" and exported_kwh > 0.0:
        net_metering_credits = round(exported_kwh * gen_rate, 2)
        line_items.append(
            BillLineItem(
                component_id="net_metering_credit",
                name="Net Metering Solar Export Credit",
                category="discounts",
                rate_applied=gen_rate,
                rate_unit="₱/kWh",
                billed_quantity=exported_kwh,
                amount=-net_metering_credits,
                vat_amount=0.0,
                total_with_vat=-net_metering_credits,
                explanation="Credit for clean solar electricity exported back to TEI at the monthly Generation Charge.",
                formula=f"{exported_kwh:.2f} kWh exported × ₱{gen_rate:.5f}/kWh (monthly TEI Generation rate)",
                vat_treatment="exempt"
            )
        )

    total_current_charges = round(subtotal_charges + total_taxes - total_discounts - net_metering_credits, 2)
    total_current_charges = max(0.0, total_current_charges)

    prev_balance = round(profile.previous_unpaid_balance, 2)
    payments = round(profile.payments_received, 2)
    total_amount_due = round(total_current_charges + prev_balance - payments, 2)
    total_amount_due = max(0.0, total_amount_due)

    effective_rate = round(total_current_charges / billed_kwh, 4) if billed_kwh > 0 else 0.0

    return StatementOfAccount(
        billing_period_start=billing_start,
        billing_period_end=billing_end,
        customer_class=schedule.customer_class,
        effective_rate_schedule_month=schedule.effective_month,
        billed_kwh=round(billed_kwh, 2),
        generation_transmission_charges=round(gen_trans_total, 2),
        distribution_charges=round(dist_total, 2),
        other_charges=round(other_total, 2),
        subtotal_electricity_charges=subtotal_charges,
        government_taxes=total_taxes,
        discounts=round(total_discounts, 2),
        net_metering_credits=net_metering_credits,
        total_current_charges=total_current_charges,
        previous_unpaid_balance=prev_balance,
        payments_received=payments,
        total_amount_due=total_amount_due,
        line_items=line_items,
        effective_average_rate_per_kwh=effective_rate,
        is_estimate=is_estimate,
        disclaimer="SolarScope Bill Estimate — Not an Official TEI Statement of Account."
    )
