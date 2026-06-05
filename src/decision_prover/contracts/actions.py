from __future__ import annotations

from typing import Any, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


JsonPrimitive: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonPrimitive | list["JsonValue"] | dict[str, "JsonValue"]
PositiveNumber: TypeAlias = float


class ActionBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str = Field(min_length=1)


class HireAction(ActionBase):
    type: Literal["hire"]
    count: int = Field(gt=0)
    role: str = Field(min_length=1)
    fully_loaded_cost_per_year: PositiveNumber = Field(gt=0)


class ChannelTestAction(ActionBase):
    type: Literal["channel_test"]
    budget: PositiveNumber | None = None
    projected_cac: PositiveNumber = Field(gt=0)
    projected_arpu_monthly: PositiveNumber = Field(gt=0)


class AcquisitionAction(ActionBase):
    type: Literal["acquisition"]
    cash_cost: PositiveNumber = Field(gt=0)
    added_mrr: PositiveNumber = Field(gt=0)
    target: str | None = None


class OneTimeSpendAction(ActionBase):
    type: Literal["one_time_spend"]
    cash_cost: PositiveNumber = Field(gt=0)
    label: str = Field(min_length=1)


class PriceChangeAction(ActionBase):
    type: Literal["price_change"]
    pct_increase: float | None = None
    scope: str | None = None
    new_unit_price: PositiveNumber | None = None
    assumed_volume_multiplier: PositiveNumber | None = None

    @model_validator(mode="after")
    def validate_price_change_shape(self) -> "PriceChangeAction":
        percent_shape = self.pct_increase is not None or self.scope is not None
        unit_price_shape = (
            self.new_unit_price is not None or self.assumed_volume_multiplier is not None
        )

        if percent_shape:
            if self.pct_increase is None or self.scope is None:
                raise ValueError(
                    "price_change percentage shape requires both 'pct_increase' and 'scope'"
                )
            if self.new_unit_price is not None or self.assumed_volume_multiplier is not None:
                raise ValueError(
                    "price_change must use either percentage fields or unit-price fields, not both"
                )

        if unit_price_shape:
            if self.new_unit_price is None or self.assumed_volume_multiplier is None:
                raise ValueError(
                    "price_change unit-price shape requires both 'new_unit_price' and "
                    "'assumed_volume_multiplier'"
                )
            if self.pct_increase is not None or self.scope is not None:
                raise ValueError(
                    "price_change must use either percentage fields or unit-price fields, not both"
                )

        if not percent_shape and not unit_price_shape:
            raise ValueError(
                "price_change must provide either {pct_increase, scope} or "
                "{new_unit_price, assumed_volume_multiplier}"
            )

        return self


class AcceptOrderAction(ActionBase):
    type: Literal["accept_order"]
    units: int = Field(gt=0)
    due_months: int = Field(gt=0)
    unit_price: PositiveNumber = Field(gt=0)


class CapexExpansionAction(ActionBase):
    type: Literal["capex_expansion"]
    cost: PositiveNumber = Field(gt=0)
    capacity_from: int = Field(gt=0)
    capacity_to: int = Field(gt=0)
    ramp_months: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_capacity_growth(self) -> "CapexExpansionAction":
        if self.capacity_to <= self.capacity_from:
            raise ValueError("'capacity_to' must be greater than 'capacity_from'")
        return self


class LaunchSkuAction(ActionBase):
    type: Literal["launch_sku"]
    launch_cost: PositiveNumber = Field(gt=0)
    projected_monthly_revenue: PositiveNumber = Field(gt=0)
    contribution_margin: PositiveNumber = Field(gt=0)


class MarketingIncreaseAction(ActionBase):
    type: Literal["marketing_increase"]
    added_monthly_spend: PositiveNumber = Field(gt=0)
    target: str = Field(min_length=1)


class DiscontinueLineAction(ActionBase):
    type: Literal["discontinue_line"]
    line: str = Field(min_length=1)
    reallocate_to: str = Field(min_length=1)


class RetentionProgramAction(ActionBase):
    type: Literal["retention_program"]
    churn_from: float = Field(ge=0)
    churn_to: float = Field(ge=0)
    cost: PositiveNumber = Field(gt=0)

    @model_validator(mode="after")
    def validate_churn_improvement(self) -> "RetentionProgramAction":
        if self.churn_to >= self.churn_from:
            raise ValueError("'churn_to' must be lower than 'churn_from'")
        return self


class SupplierRenegotiationAction(ActionBase):
    type: Literal["supplier_renegotiation"]
    cost: float = Field(ge=0)
    line_A_cogs_reduction_pts: float = Field(gt=0)


def _is_json_compatible(value: Any) -> bool:
    if value is None or isinstance(value, (str, int, float, bool)):
        return True
    if isinstance(value, list):
        return all(_is_json_compatible(item) for item in value)
    if isinstance(value, dict):
        return all(isinstance(key, str) and _is_json_compatible(item) for key, item in value.items())
    return False


class GenericActionPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_extras(self) -> "GenericActionPayload":
        extras = self.model_extra or {}
        if not extras:
            raise ValueError("generic actions require at least one parameter besides 'type'")
        for key, value in extras.items():
            if not key:
                raise ValueError("generic action parameter names must be non-empty strings")
            if not _is_json_compatible(value):
                raise ValueError(
                    f"generic action parameter '{key}' must be JSON-compatible, got {type(value).__name__}"
                )
        return self


ActionPayload: TypeAlias = (
    HireAction
    | ChannelTestAction
    | AcquisitionAction
    | OneTimeSpendAction
    | PriceChangeAction
    | AcceptOrderAction
    | CapexExpansionAction
    | LaunchSkuAction
    | MarketingIncreaseAction
    | DiscontinueLineAction
    | RetentionProgramAction
    | SupplierRenegotiationAction
    | GenericActionPayload
)

ACTION_REGISTRY = {
    "hire": HireAction,
    "channel_test": ChannelTestAction,
    "acquisition": AcquisitionAction,
    "one_time_spend": OneTimeSpendAction,
    "price_change": PriceChangeAction,
    "accept_order": AcceptOrderAction,
    "capex_expansion": CapexExpansionAction,
    "launch_sku": LaunchSkuAction,
    "marketing_increase": MarketingIncreaseAction,
    "discontinue_line": DiscontinueLineAction,
    "retention_program": RetentionProgramAction,
    "supplier_renegotiation": SupplierRenegotiationAction,
}


def validate_action_payload(value: Any) -> ActionPayload:
    if not isinstance(value, dict):
        raise TypeError("action payload must be an object")

    action_type = value.get("type")
    if not isinstance(action_type, str) or not action_type.strip():
        raise ValueError("action.type must be a non-empty string")

    model = ACTION_REGISTRY.get(action_type, GenericActionPayload)
    try:
        return model.model_validate(value)
    except ValidationError:
        raise
