# Compila la tesis y publica el PDF en docs/ para que quede versionado en GitHub.
# Las fuentes viven en escritos/, que sincroniza con Overleaf via git subtree,
# por eso el PDF se copia afuera: no debe viajar al proyecto de Overleaf.

ESCRITOS = escritos
PDF      = docs/tesis.pdf

.PHONY: tesis watch clean

# Build completo + publicacion del entregable.
tesis:
	cd $(ESCRITOS) && latexmk -pdf -interaction=nonstopmode main.tex
	@mkdir -p docs
	@cp $(ESCRITOS)/main.pdf $(PDF)
	@echo "==> $(PDF) actualizado"

# Recompila solo al guardar, para escribir.
watch:
	cd $(ESCRITOS) && latexmk -pdf -pvc -interaction=nonstopmode -view=none main.tex

clean:
	cd $(ESCRITOS) && latexmk -C
