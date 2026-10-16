.PHONY: install run test lint clean

install:
	./install.sh

run:
	@test -d .venv || (echo "[ERROR] .venv no existe. Corre 'make install' primero." && exit 1)
	.venv/bin/python -m jarvis_local.cli

test:
	QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest test/ -q

lint:
	.venv/bin/python -m ruff check .

clean:
	rm -rf .venv
