# Job Raider - Example Notebooks

This directory contains Jupyter notebooks demonstrating Job Raider usage.

## Notebooks

### example_usage.ipynb
A comprehensive walkthrough of Job Raider's key features:
- Creating user profiles
- Scraping job listings
- Scoring and ranking jobs
- Resume content selection
- Cost tracking
- Outcome tracking

## Running the Notebooks

1. Activate the virtual environment:
```bash
source .venv/bin/activate
```

2. Install Jupyter:
```bash
pip install jupyter notebook
```

3. Start Jupyter:
```bash
jupyter notebook
```

4. Navigate to the `notebooks` directory and open a notebook.

## Notes

- Some notebooks may require API keys (set in `.env`)
- Scraping examples are designed to be dry-run by default
- Cost estimates use local models (Ollama) by default
