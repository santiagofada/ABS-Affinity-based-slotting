# Compila la tesis y copia el PDF a docs/ para verlo localmente.
# Las fuentes viven en escritos/, que sincroniza con Overleaf via git subtree,
# por eso el PDF se copia afuera: no debe viajar al proyecto de Overleaf.
#
# REGLA: docs/tesis.pdf lo commitea SOLO el GitHub Action. Localmente se
# compila y se mira, pero no se agrega a los commits; si no, cada pull choca
# con el commit del bot (dos versiones del mismo binario).

ESCRITOS = escritos
PDF      = docs/tesis.pdf

.PHONY: tesis watch clean empezar traer mandar

# Build completo + publicacion del entregable.
tesis:
	cd $(ESCRITOS) && latexmk -pdf -shell-escape -interaction=nonstopmode main.tex
	@mkdir -p docs
	@cp $(ESCRITOS)/main.pdf $(PDF)
	@echo "==> $(PDF) actualizado (no commitear, lo sube el Action)"

# Recompila solo al guardar, para escribir.
watch:
	cd $(ESCRITOS) && latexmk -pdf -pvc -shell-escape -interaction=nonstopmode -view=none main.tex

clean:
	cd $(ESCRITOS) && latexmk -C

# ---------------------------------------------------------------------------
# Sincronizacion con Overleaf
# ---------------------------------------------------------------------------

# Antes de escribir: trae los commits del bot (el PDF) y lo que escribio el
# director en Overleaf. Siempre merge, nunca rebase (un rebase sobre los
# squash del subtree rompe el historial). Si hay cambios sin commitear fuera
# de escritos/, se guardan en un stash mientras corre el subtree pull y se
# restauran al final. Si docs/tesis.pdf esta modificado localmente, se
# descarta antes del pull para quedarse con el del bot.
empezar: traer

traer:
	@git diff --quiet -- $(PDF) || { echo "==> descarto $(PDF) local, manda el del Action"; git checkout -- $(PDF); }
	git pull --no-rebase
	@if ! git diff-index --quiet HEAD --; then \
		echo "==> guardo cambios sin commitear en un stash mientras corre el subtree pull"; \
		git stash push -q -m "make traer"; \
		git subtree pull --prefix=$(ESCRITOS) overleaf main --squash -m "escritos: traer cambios de overleaf" || { git stash pop -q; exit 1; }; \
		git stash pop -q; \
	else \
		git subtree pull --prefix=$(ESCRITOS) overleaf main --squash -m "escritos: traer cambios de overleaf"; \
	fi

# Al terminar. Ojo: subtree push manda lo COMMITEADO, no el working tree.
mandar:
	@git diff-index --quiet HEAD -- $(ESCRITOS) || \
		{ echo "ERROR: tenes cambios sin commitear en $(ESCRITOS)/. Commitealos primero."; exit 1; }
	@git diff --quiet -- $(PDF) || \
		echo "AVISO: $(PDF) esta modificado localmente; no lo commitees, lo regenera el Action."
	git push
	git subtree push --prefix=$(ESCRITOS) overleaf main
