import hashlib
import os

artifacts = [
    'location_ranker_v4.joblib',
    'location_calibrator_v4.joblib',
    'time_regressor_v3.joblib',
    'feature_schema_v4.json',
    'model_metadata_v4.json'
]
for a in artifacts:
    p = os.path.join('ml', 'artifacts', a)
    if os.path.exists(p):
        with open(p, 'rb') as f:
            h = hashlib.sha256(f.read()).hexdigest()
        print(f'"{a}": "{h}",')
