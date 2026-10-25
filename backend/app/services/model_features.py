"""Order-time-only feature transformations, shared by fit and inference."""
import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin

NUMERIC = ["scheduled_days", "quantity", "net_sales", "item_count", "day_of_week", "month"]
CATEGORICAL = ["market", "region", "customer_segment", "payment_type"]
FEATURES = NUMERIC + CATEGORICAL
GROUPS = {
    "shipping_schedule": ("Scheduled shipping days", ["scheduled_days"]),
    "basket_size": ("Basket size", ["quantity", "item_count"]),
    "order_value": ("Net order value", ["net_sales"]),
    "weekday": ("Order weekday", ["day_of_week"]),
    "month": ("Order month", ["month"]),
    "destination": ("Destination market and region", ["market", "region"]),
    "customer_segment": ("Customer segment", ["customer_segment"]),
    "payment_type": ("Payment type", ["payment_type"]),
}


class OrderFeatures(BaseEstimator, TransformerMixin):
    def __init__(self, variant="numeric"):
        self.variant = variant

    def fit(self, X, y=None):
        self.feature_names_in_ = np.array(FEATURES, dtype=object)
        return self

    def transform(self, X):
        # Explicit allowlist excludes IDs, outcomes and arbitrary extra columns.
        result = X[FEATURES].copy()
        if self.variant == "cyclical":
            for name, period in [("day_of_week", 7), ("month", 12)]:
                angle = 2 * np.pi * (result[name] - 1) / period
                result[name + "_sin"] = np.sin(angle)
                result[name + "_cos"] = np.cos(angle)
            result = result.drop(columns=["day_of_week", "month"])
        if self.variant == "basket":
            result["net_per_unit"] = result.net_sales / result.quantity
            result["net_per_line"] = result.net_sales / result.item_count
            result["units_per_line"] = result.quantity / result.item_count
        return result[numeric_features(self.variant) + CATEGORICAL]

    def get_feature_names_out(self, input_features=None):
        return np.array(numeric_features(self.variant) + CATEGORICAL, dtype=object)


def numeric_features(variant):
    if variant == "cyclical":
        return NUMERIC[:4] + ["day_of_week_sin", "day_of_week_cos", "month_sin", "month_cos"]
    return NUMERIC + (["net_per_unit", "net_per_line", "units_per_line"] if variant == "basket" else [])
