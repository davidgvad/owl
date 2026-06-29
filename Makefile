.PHONY: run validate

run:
	./run_local.sh

validate:
	python3 scripts/validate_mission.py data/calibrated_mission
