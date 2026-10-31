"""
labels.py - congestion labels agreed with the Jungle Brew manager
Okay       : average wait <= 7 minutes
Congested  : more than 7 and up to 15 minutes
Overloaded : more than 15 minutes
"""
OKAY_MAX = 7.0
CONGESTED_MAX = 15.0
CLASSES = ["Okay", "Congested", "Overloaded"]


def label(avg_wait):
    if avg_wait <= OKAY_MAX:
        return "Okay"
    if avg_wait <= CONGESTED_MAX:
        return "Congested"
    return "Overloaded"


def add_load_features(row):
    """Queueing-theory 'load' features: how busy each station is expected to be.
    A value near or above 1.0 means the station cannot keep up."""
    drink_time = row["p_simple"] * row["simple_prep"] + (1 - row["p_simple"]) * row["complex_prep"]
    row["barista_load"] = row["arr_rate"] * drink_time / row["num_barista"]
    row["cashier_load"] = row["arr_rate"] * row["cashier_mean"] / row["num_cashier"]
    return row


BASE_FEATURES = ["arr_rate", "p_simple", "num_cashier", "num_barista",
                 "cashier_mean", "simple_prep", "complex_prep"]
FEATURES = BASE_FEATURES + ["barista_load", "cashier_load"]
