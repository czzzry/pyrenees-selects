.PHONY: demo test

demo:
	python3 scripts/run_synthetic_demo.py

test:
	python3 -m unittest discover -s tests
	python3 -m compileall -q pyrenees_selects scripts tests
	node --check pyrenees_selects/static/app.js
