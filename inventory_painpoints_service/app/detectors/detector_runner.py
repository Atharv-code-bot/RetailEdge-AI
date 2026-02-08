# app/detectors/detector_runner.py

import pandas as pd

from app.detectors.declining_sales import detect_declining_sales
from app.detectors.stagnant_sales import detect_stagnant_sales
from app.detectors.low_stock import detect_low_stock
from app.detectors.overstock import detect_overstock
from app.detectors.seasonal_mismatch import detect_seasonal_mismatch


def run_all_detectors(features_df: pd.DataFrame) -> pd.DataFrame:
    detectors = [
        detect_declining_sales,
        detect_stagnant_sales,
        detect_low_stock,
        detect_overstock,
        detect_seasonal_mismatch,
    ]

    results = []

    for detector in detectors:
        detected = detector(features_df)
        if not detected.empty:
            results.append(detected)

    if not results:
        return pd.DataFrame()

    return pd.concat(results, ignore_index=True)
