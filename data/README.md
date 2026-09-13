# Data

MachineGuard uses the UCI **Condition Monitoring of Hydraulic Systems** dataset (DOI `10.24432/C5CW21`, CC BY 4.0). It contains real measurements from a hydraulic test rig across 2,205 operating cycles, with 17 sensors sampled at different frequencies.

Run `python scripts/prepare_hydraulic_data.py` after downloading/extracting the official archive. The preparation script aggregates each 60-second cycle into five operational features:

- PS1 mean pressure (`pressure_bar`)
- TS1 mean oil temperature (`oil_temperature_c`)
- EPS1 mean motor power (`motor_power_w`)
- FS1 mean volume flow (`volume_flow_lpm`)
- VS1 mean vibration (`vibration_mms`)

The supervised target is severe internal pump leakage (`pump_leakage_class >= 2`). Condition labels are excluded from predictors. `HYD-####` identifies an operating cycle in the benchmark—not a unique physical production machine.

`processed/hydraulic_cycles.csv` is the model-ready table. Raw archive contents are intentionally ignored by Git; see the official source at https://archive.ics.uci.edu/dataset/447.
