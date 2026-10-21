# Convenience targets; every target is a thin wrapper over `python -m smartcity.cli`.
PY ?= python

.PHONY: install test lint doctor audit preprocess graph features baselines proposed ablations evaluate calibrate \
        explain rag simulation agents export paper verify api dashboard worker

install:
	$(PY) -m pip install -e .[dev]

test:
	$(PY) -m pytest -q tests

lint:
	ruff check src tests scripts

doctor:
	$(PY) -m smartcity.cli doctor

audit:
	$(PY) -m smartcity.cli data audit

preprocess:
	$(PY) -m smartcity.cli data preprocess

graph:
	$(PY) -m smartcity.cli graph build && $(PY) -m smartcity.cli graph validate

features:
	$(PY) -m smartcity.cli features build --track operational && $(PY) -m smartcity.cli features build --track retrospective

baselines:
	$(PY) -m smartcity.cli train baselines --track operational

proposed:
	$(PY) -m smartcity.cli train proposed --track operational

ablations:
	$(PY) -m smartcity.cli train proposed --track operational --variants ablation_no_gate,ablation_no_weather,ablation_no_infrastructure,ablation_no_events,ablation_no_incidents
	$(PY) -m smartcity.cli evaluate ablations --track operational

evaluate:
	$(PY) -m smartcity.cli evaluate forecasts --track operational

calibrate:
	$(PY) -m smartcity.cli uncertainty calibrate --track operational

explain:
	$(PY) -m smartcity.cli explain alerts --track operational

rag:
	$(PY) -m smartcity.cli rag build && $(PY) -m smartcity.cli rag evaluate

simulation:
	$(PY) -m smartcity.cli simulation prepare && $(PY) -m smartcity.cli simulation select-demand && $(PY) -m smartcity.cli simulation evaluate

agents:
	$(PY) -m smartcity.cli agents evaluate

export:
	$(PY) -m smartcity.cli report export

paper:
	$(PY) -m smartcity.cli paper sync && cd paper && pdflatex -interaction=nonstopmode main.tex && bibtex main && pdflatex -interaction=nonstopmode main.tex && pdflatex -interaction=nonstopmode main.tex

verify:
	$(PY) -m smartcity.cli verify all

api:
	uvicorn smartcity.api.app:app --host 0.0.0.0 --port 8000

worker:
	$(PY) -m smartcity.api.worker

dashboard:
	streamlit run src/smartcity/dashboard/app.py
