# EXL Take-Home: OmniRetail Data Management Pipeline

## Setup

```bash
pip install -r requirements.txt
```

## Run the pipeline

```bash
python src/pipeline.py
```

## Run tests

```bash
pytest tests/
```

## Outputs

| File | Description |
|---|---|
| `outputs/curated.sqlite` | Curated SQLite database with all five tables |
| `outputs/data_quality_report.md` | DQ rule results (DQ001–DQ012) |
| `outputs/exceptions.csv` | Records that failed FK or value checks |
| `outputs/business_answers.md` | Answers to the five business questions |
