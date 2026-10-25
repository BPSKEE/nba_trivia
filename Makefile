.DEFAULT_GOAL := build

.PHONY: build
build:
	.venv/bin/python build_app.py

.PHONY: mobile-data mobile-serve
mobile-data:
	.venv/bin/python build_mobile.py

mobile-serve:
	.venv/bin/python -m http.server 8080 --directory mobile/dist

.PHONY: website website-serve
website:
	.venv/bin/python build_mobile.py

website-serve:
	.venv/bin/python -m http.server 8080 --directory docs
