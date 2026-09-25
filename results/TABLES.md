# FinBench closed-book results

Intervals are Wilson 90%. Confident-wrong is the headline; numeric accuracy is the control.

| Model | n | Confident-wrong | Numeric accuracy | Fabrication | Format |
|---|---:|---|---|---|---|
| claude-opus-5 | 1074 | 0.3% (3/1074; 0.1–0.7) | 9.2% (63/684; 7.5–11.2) | 0.0% (0/114; 0.0–2.3) | 99.4% (1068/1074; 98.9–99.7) |
| gemini-3.1-pro | 1074 | 0.2% (2/1074; 0.1–0.6) | 2.5% (17/684; 1.7–3.7) | 0.0% (0/114; 0.0–2.3) | 100.0% (1074/1074; 99.7–100.0) |
| gpt-5.6-luna | 1074 | 20.8% (223/1074; 18.8–22.9) | 2.5% (17/669; 1.7–3.7) | 0.0% (0/114; 0.0–2.3) | 100.0% (1074/1074; 99.7–100.0) |
| gpt-5.6-sol | 1074 | 5.5% (59/1074; 4.5–6.8) | 11.5% (77/669; 9.6–13.7) | 0.0% (0/114; 0.0–2.3) | 100.0% (1074/1074; 99.7–100.0) |
| grok-4.6 | 1074 | 0.1% (1/1074; 0.0–0.4) | 4.4% (30/675; 3.3–5.9) | 0.0% (0/114; 0.0–2.3) | 100.0% (1074/1074; 99.7–100.0) |
| sonar-pro | 1074 | 36.2% (389/1074; 33.8–38.7) | 58.6% (478/816; 55.7–61.4) | 4.4% (5/114; 2.2–8.7) | 100.0% (1074/1074; 99.7–100.0) |

## Calibration

- **claude-opus-5**: ECE 0.343, Brier 0.284, confidence AUC 0.403, behavioral -0.002
- **gemini-3.1-pro**: ECE 0.307, Brier 0.308, confidence AUC 0.747, behavioral -0.545
- **gpt-5.6-luna**: ECE 0.593, Brier 0.588, confidence AUC 0.587, behavioral -1.446
- **gpt-5.6-sol**: ECE 0.48, Brier 0.417, confidence AUC 0.729, behavioral -0.783
- **grok-4.6**: ECE 0.402, Brier 0.406, confidence AUC 0.543, behavioral -0.528
- **sonar-pro**: ECE 0.401, Brier 0.397, confidence AUC 0.667, behavioral -0.748

## Coverage

- **claude-opus-5**: 1074 scored, 0 retried once, 0 still failed, 0 quarantined (substitution)
- **gemini-3.1-pro**: 1074 scored, 3 retried once, 0 still failed, 0 quarantined (substitution)
- **gpt-5.6-luna**: 1074 scored, 0 retried once, 0 still failed, 0 quarantined (substitution)
- **gpt-5.6-sol**: 1074 scored, 1 retried once, 0 still failed, 0 quarantined (substitution)
- **grok-4.6**: 1074 scored, 0 retried once, 0 still failed, 0 quarantined (substitution)
- **sonar-pro**: 1074 scored, 0 retried once, 0 still failed, 0 quarantined (substitution)
