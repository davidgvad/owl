.PHONY: run test validate

run:
	./run_local.sh

test:
	PYTHONPYCACHEPREFIX=/private/tmp/owl_pycache python3 -m unittest tests.pipeowl_tests
	ctest --test-dir build

validate:
	python3 scripts/validate_mission.py data/demo_mission
