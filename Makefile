.PHONY: install gen drift test capture check dump clean

VENV := .venv
PY := $(VENV)/bin/python

install:            ## install node + python toolchains (pinned)
	npm install
	python3 -m venv $(VENV)
	$(PY) -m pip install -q --upgrade pip
	$(PY) -m pip install -q -e '.[codegen,dev]'

gen:                ## regenerate schema + Pydantic models from pinned pi
	bash scripts/generate.sh

drift:              ## fail if committed schema/models differ from generation
	bash scripts/check_drift.sh

test:               ## run pytest over the committed session fixture
	$(PY) -m pytest -q

capture:            ## drive local `pi --mode rpc`, save sessions/local.jsonl
	$(PY) scripts/capture_session.py --out sessions/local.jsonl

check:              ## parse a captured session and report coverage + drift
	$(PY) scripts/check_session.py sessions/local.jsonl

dump:               ## parse the session and dump collected Pydantic models to a file
	$(PY) scripts/dump_models.py sessions/local.jsonl sessions/local.parsed.jsonl

clean:
	rm -rf $(VENV) node_modules
