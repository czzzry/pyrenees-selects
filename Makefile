.PHONY: demo test test-browser onboarding-prototype

demo:
	python3 scripts/run_synthetic_demo.py

test:
	python3 -m unittest discover -s tests
	python3 -m compileall -q pyrenees_selects scripts tests
	node --check pyrenees_selects/static/app.js
	node --check pyrenees_selects/static/preeditor.js
	sh -n scripts/bootstrap_selects.sh scripts/run_selects.sh
	zsh -n scripts/build_selects_macos_app.sh scripts/generate_selects_icon.sh

test-browser:
	npm run test:ui

onboarding-prototype:
	python3 -m http.server 4173
