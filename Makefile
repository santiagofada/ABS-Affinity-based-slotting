# Compila la tesis y publica el PDF en docs/ para que quede versionado en GitHub.
# Las fuentes viven en escritos/, que sincroniza con Overleaf via git subtree,
# por eso el PDF se copia afuera: no debe viajar al proyecto de Overleaf.

ESCRITOS = escritos
PDF      = docs/tesis.pdf

.PHONY: tesis watch clean empezar traer mandar

# Build completo + publicacion del entregable.
tesis:
	cd $(ESCRITOS) && latexmk -pdf -shell-escape -interaction=nonstopmode main.tex
	@mkdir -p docs
	@cp $(ESCRITOS)/main.pdf $(PDF)
	@echo "==> $(PDF) actualizado"

# Recompila solo al guardar, para escribir.
watch:
	cd $(ESCRITOS) && latexmk -pdf -pvc -shell-escape -interaction=nonstopmode -view=none main.tex

clean:
	cd $(ESCRITOS) && latexmk -C

# ---------------------------------------------------------------------------
# Sincronizacion con Overleaf
# ---------------------------------------------------------------------------

# Antes de escribir: trae los commits del bot (el PDF) y lo que escribio el
# director en Overleaf.
empezar: traer

traer:
	git pull
	git subtree pull --prefix=$(ESCRITOS) overleaf main --squash

# Al terminar. Ojo: subtree push manda lo COMMITEADO, no el working tree.
mandar:
	@git diff-index --quiet HEAD -- $(ESCRITOS) || \
		{ echo "ERROR: tenes cambios sin commitear en $(ESCRITOS)/. Commitealos primero."; exit 1; }
	git push
	git subtree push --prefix=$(ESCRITOS) overleaf main
