RAW_FEATURES = [
    "type",
    "air_temperature",
    "process_temperature",
    "rotational_speed",
    "torque",
    "tool_wear",
]
NUMERIC_FEATURES = [
    "air_temperature",
    "process_temperature",
    "rotational_speed",
    "torque",
    "tool_wear",
    "temperature_difference",
    "power_proxy",
    "wear_torque_interaction",
]
CATEGORICAL_FEATURES = ["type"]
LEAKAGE_COLUMNS = ["twf", "hdf", "pwf", "osf", "rnf"]
TARGET = "machine_failure"
RANDOM_SEED = 42
