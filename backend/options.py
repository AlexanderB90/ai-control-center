"""Expiry payoffs for fully covered, unadjusted physical equity options."""
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

Money = Annotated[Decimal, Field(ge=0, le=1000000000, max_digits=15, decimal_places=4, allow_inf_nan=False)]
Price = Annotated[Decimal, Field(gt=0, le=1000000, max_digits=12, decimal_places=4, allow_inf_nan=False)]
Count = Annotated[int, Field(strict=True, ge=1, le=10000)]
ZERO = Decimal("0")
VERSION = "0.1.0"


def today():
    return datetime.now(ZoneInfo("Europe/Copenhagen")).date()


class OptionsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    strategy: Literal["covered_call", "cash_secured_put"]
    symbol: Annotated[str, Field(min_length=1, max_length=24, pattern=r"^[A-Za-z0-9.\-]+$")]
    currency: Literal["USD", "DKK", "EUR", "GBP"]
    spot: Price
    strike: Price
    premium: Money  # Per share, not per contract.
    contracts: Count
    contract_size: Count
    fees: Money  # Fixed total fees across the whole strategy, including assignment.
    expiry: date
    quote_at: AwareDatetime
    source: Annotated[str, Field(min_length=1, max_length=120)]
    goal: Literal["income", "keep_shares", "sell_shares", "buy_shares"]
    standard_contract: Literal[True]
    shares_owned: Annotated[int, Field(strict=True, ge=0, le=100000000)] = 0
    cost_basis: Price | None = None
    cash_available: Money | None = None

    @model_validator(mode="after")
    def validate_trade(self):
        if self.expiry <= today():
            raise ValueError("Udløb skal være efter i dag; 0DTE understøttes ikke.")
        if (self.quote_at - datetime.now(self.quote_at.tzinfo)).total_seconds() > 300:
            raise ValueError("Kurstidspunkt må ikke ligge i fremtiden.")
        if not self.source.strip():
            raise ValueError("Angiv en datakilde.")
        units = self.contracts * self.contract_size
        if self.strategy == "covered_call":
            if self.cost_basis is None or self.shares_owned < units:
                raise ValueError("Covered call kræver købspris og tilstrækkeligt antal aktier.")
            if self.premium >= self.spot:
                raise ValueError("Call-præmie pr. aktie skal være mindre end aktiekursen.")
        else:
            if self.cash_available is None or self.cash_available < self.strike * units + self.fees:
                raise ValueError("Kontanter skal dække strike × antal aktier plus samlede gebyrer.")
            if self.premium >= self.strike:
                raise ValueError("Put-præmie pr. aktie skal være mindre end strike.")
        return self


def rounded(value):
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def calculate(trade: OptionsRequest):
    units = Decimal(trade.contracts * trade.contract_size)
    net = trade.premium * units - trade.fees
    per_share = net / units
    call = trade.strategy == "covered_call"
    reference = trade.spot if call else trade.strike
    best = (trade.strike - reference) * units + net if call else net
    worst = -reference * units + net
    raw_break_even = reference - per_share

    def breakeven(value):
        # Both payoff curves plateau at strike. A root beyond the cap is invalid.
        return rounded(value) if 0 <= value <= trade.strike else None

    warnings = [
        "Manuelle data; kurser og præmier er ikke verificeret eller hentet live.",
        "Scenarier gælder ved udløb. De er ikke prognoser eller sandsynligheder.",
        "Skat, valutaændringer, udbytte, renter og tidligere optionspræmier er udeladt.",
        "Gebyrer er dit faste samlede skøn. Faktiske omkostninger og udførelsespris kan afvige.",
        "Førtidig tildeling kan ske for amerikanske optioner. Ved strike er tildeling usikker.",
        "Regnskab, ex-udbytte, nyheder, spread, likviditet, IV og Greeks er ikke kontrolleret.",
    ]
    age = (datetime.now(trade.quote_at.tzinfo) - trade.quote_at).total_seconds()
    if age > 86400:
        warnings.append("De indtastede kursdata er over 24 timer gamle.")
    if net <= 0:
        warnings.append("Nettopræmien er nul eller negativ efter gebyrer.")
    intrinsic = max(ZERO, trade.spot - trade.strike if call else trade.strike - trade.spot)
    if trade.premium < intrinsic:
        warnings.append("Præmien er under indre værdi. Kontrollér pris, enhed og tidspunkt.")
    if call and trade.goal == "keep_shares":
        warnings.append("Covered call kan medføre salg og konflikter med ønsket om at beholde aktierne.")
    if (call and trade.goal == "buy_shares") or (not call and trade.goal in ("keep_shares", "sell_shares")):
        warnings.append("Det valgte mål passer ikke direkte til strategien.")
    if call and (trade.strike - trade.cost_basis) * units + net < 0:
        warnings.append("Selv bedste udløbsresultat er et tab i forhold til din købspris.")
    warnings.append(
        "Aktietabet kan være stort; kursgevinst over strike afgives på den dækkede del."
        if call else
        "Du kan blive forpligtet til at købe til strike, selv efter et stort kursfald."
    )
    prices = {ZERO, trade.strike, *(trade.spot * Decimal(f)
               for f in ("0.5", "0.8", "0.9", "1", "1.1", "1.2"))}
    if breakeven(raw_break_even) is not None:
        prices.add(raw_break_even)
    cost_break_even = trade.cost_basis - per_share if call else None
    if call and breakeven(cost_break_even) is not None:
        prices.add(cost_break_even)
    rows = []
    for price in sorted(prices):
        liability = max(ZERO, price - trade.strike if call else trade.strike - price) * units
        option_pl = net - liability
        total = (price - trade.spot) * units + option_pl if call else option_pl
        cost_pl = (price - trade.cost_basis) * units + option_pl if call else None
        assignment = ("Usikker ved strike" if price == trade.strike else
                      "Tildeling forventes" if (price > trade.strike if call else price < trade.strike)
                      else "Normalt ingen tildeling")
        rows.append({
            "price": rounded(price), "option_pl": rounded(option_pl),
            "total_pl": rounded(total), "cost_basis_pl": rounded(cost_pl) if call else None,
            "hold_shares_pl": rounded((price - trade.spot) * units) if call else None,
            "assignment": assignment,
        })
    return {
        "calculation_version": VERSION, "calculated_at": datetime.now().astimezone().isoformat(),
        "input": trade.model_dump(mode="json"), "days_to_expiry": (trade.expiry - today()).days,
        "units": int(units), "gross_premium": rounded(trade.premium * units),
        "net_premium": rounded(net),
        "premium_yield_pct": rounded(net / (reference * units) * 100),
        "yield_basis": "Aktiernes aktuelle værdi" if call else "Strike × antal aktier",
        "capital_reference": rounded(reference * units),
        "cash_required": rounded(trade.strike * units + trade.fees) if not call else None,
        "effective_assignment_price": rounded(trade.strike + per_share if call else trade.strike - per_share),
        "best_expiry_pl": rounded(best), "max_loss": rounded(max(ZERO, -worst)),
        "break_even": breakeven(raw_break_even),
        "best_cost_basis_pl": rounded((trade.strike - trade.cost_basis) * units + net) if call else None,
        "cost_basis_break_even": breakeven(cost_break_even) if call else None,
        "cost_basis_max_loss": rounded(max(ZERO, trade.cost_basis * units - net)) if call else None,
        "warnings": warnings, "scenarios": rows,
    }
