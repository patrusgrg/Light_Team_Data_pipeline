# Research Pipeline

Multi-sensor ecological monitoring system for studying nocturnal biological activity under artificial light.

exppected folder structure before running .
20260412_I/
  20260412_I_SM4/         ← .wav or .wac files from SM4
  20260412_I_SQM/         ← single CSV from SQM SD card
  20260412_I_HOBO/        ← 6 CSV exports from HOBOware (HOBO-01 … HOBO-06)
  20260412_I_SPEC/        ← raw spectral files + dark frames
  20260412_I_THERMAL/     ← video or image files from thermal camera
  20260412_I_LUX/         ← lux field card scan + display photos
  20260412_I_ADMIN/       ← Field Log, Time Sync Sheet, treatment photos


  expexted output :
  20260412_I/
  manifest.csv                                        ← SOP 12 checksum manifest
  20260412_I_SQM/
    20260412_I_SQM_SQM-01_2100UTC_summary.json        ← SQM nightly stats
  20260412_I_HOBO/
    hobo_transect_summary.json                        ← all 6 loggers + gradient
  20260412_I_ADMIN/
    nightly_qa_report.txt                             ← human-readable QA summary
    nightly_qa_report.json                            ← machine-readable version