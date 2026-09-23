# FinBench closed-book results

Run `dfba4ccd2d88` on 2026-09-18. 6,444 planned calls, 6,436 scored, 8
timeouts (unscored), $20.25, zero provider substitutions. Gold is still
`verification: auto` — treat these numbers as a working run, not the
published result, until the human sheet is applied.

Intervals are Wilson 90%. Confident-wrong is the headline; numeric accuracy is the control.

| Model | n | Confident-wrong | Numeric accuracy | Fabrication | Format |
|---|---:|---|---|---|---|
| claude-opus-5 | 1073 | 0.6% (6/1073; 0.3–1.1) | 10.5% (72/683; 8.8–12.6) | 0.0% (0/114; 0.0–2.3) | 99.7% (1070/1073; 99.3–99.9) |
| gemini-3.1-pro | 1072 | 0.0% (0/1072; 0.0–0.3) | 0.9% (6/682; 0.5–1.7) | 0.0% (0/114; 0.0–2.3) | 100.0% (1072/1072; 99.7–100.0) |
| gpt-5.6-luna | 1074 | 19.7% (212/1074; 17.8–21.8) | 2.4% (16/669; 1.6–3.6) | 0.0% (0/114; 0.0–2.3) | 100.0% (1074/1074; 99.7–100.0) |
| gpt-5.6-sol | 1071 | 5.7% (61/1071; 4.6–7.0) | 11.9% (79/666; 10.0–14.1) | 0.0% (0/114; 0.0–2.3) | 100.0% (1071/1071; 99.7–100.0) |
| grok-4.6 | 1072 | 0.1% (1/1072; 0.0–0.4) | 4.2% (28/673; 3.1–5.6) | 0.0% (0/114; 0.0–2.3) | 100.0% (1072/1072; 99.7–100.0) |
| sonar-pro | 1074 | 6.4% (69/1074; 5.3–7.8) | 0.1% (1/816; 0.0–0.5) | 0.9% (1/114; 0.2–3.8) | 100.0% (1074/1074; 99.7–100.0) |

## Calibration

- **claude-opus-5**: ECE 0.334, Brier 0.284, confidence AUC 0.416, behavioral -0.013
- **gemini-3.1-pro**: ECE 0.347, Brier 0.345, confidence AUC 0.698, behavioral -0.58
- **gpt-5.6-luna**: ECE 0.59, Brier 0.572, confidence AUC 0.601, behavioral -1.399
- **gpt-5.6-sol**: ECE 0.463, Brier 0.401, confidence AUC 0.742, behavioral -0.744
- **grok-4.6**: ECE 0.386, Brier 0.389, confidence AUC 0.546, behavioral -0.451
- **sonar-pro**: ECE 0.202, Brier 0.183, confidence AUC 0.439, behavioral -0.206
