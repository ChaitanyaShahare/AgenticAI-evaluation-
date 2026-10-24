# Thin wrapper over the `evalkit` CLI. Windows without make: run the right-hand command directly,
# for example `uv run evalkit smoke` instead of `make smoke`.
# Keep the virtual environment outside Dropbox: set UV_PROJECT_ENVIRONMENT (see docs/setup.md).

PROJECT ?= kyc_onboarding
EVALKIT = uv run --frozen evalkit
ARGS    = --project $(PROJECT)

.PHONY: help setup nlp doctor data data-check test smoke cases lint-cases coverage eval gate full report calibrate lab lint

help:            ## list targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | sed 's/:.*##/ —/'

setup:           ## install the pinned environment from uv.lock
	uv sync --frozen

nlp:             ## optional spaCy model (~600 MB); not needed — the PII checks are regex + checksums
	uv run --frozen python -m spacy download en_core_web_lg

doctor:          ## check Python, configuration, seed data, API key and NLP model
	$(EVALKIT) doctor $(ARGS)

data:            ## rebuild the synthetic seed database and run the fixture check
	$(EVALKIT) data $(ARGS)

data-check:      ## only run the fixture check on the current seed database
	$(EVALKIT) data --check-only $(ARGS)

test:            ## framework tests (no live API calls)
	$(EVALKIT) test

smoke:           ## quick confidence run
	$(EVALKIT) smoke $(ARGS)

lint:            ## ruff + yamllint
	uv run --frozen ruff check .
	uv run --frozen yamllint configs projects

# ---- registered now, built in later work packages (each prints its plan date)
cases:           ## [WP6] catalogue workbook -> datasets/**/*.yaml
	$(EVALKIT) cases $(ARGS)
lint-cases:      ## [WP6] check case YAML
	$(EVALKIT) lint-cases $(ARGS)
coverage:        ## [WP6] agent x pattern coverage matrix
	$(EVALKIT) coverage $(ARGS)
eval:            ## [WP4] one case: make eval CASE=KYC-EDG-014 TRIALS=3 (dry run; add YES=1 to run live)
	$(EVALKIT) eval $(ARGS) --case $(CASE) $(if $(TRIALS),--trials $(TRIALS)) $(if $(YES),--yes)
gate:            ## [WP5] all S1 cases, k = 3, judges off (dry run; YES=1 runs live)
	$(EVALKIT) gate $(ARGS) $(if $(YES),--yes)
full:            ## [WP8] all cases with judges (dry run; YES=1 runs live)
	$(EVALKIT) full $(ARGS) $(if $(YES),--yes)
report:          ## [WP8] rebuild report.html: make report RUN=<run id>
	$(EVALKIT) report $(ARGS) $(RUN)
calibrate:       ## [WP7] judge calibration
	$(EVALKIT) calibrate $(ARGS)
lab:             ## [WP10] bug-hunt lab: make lab VARIANT=LAB-3 CASE=KYC-PII-042 (dry run; YES=1 runs live)
	$(EVALKIT) lab $(ARGS) --variant $(VARIANT) $(if $(CASE),--case $(CASE)) $(if $(MODE),--mode $(MODE)) $(if $(YES),--yes)
