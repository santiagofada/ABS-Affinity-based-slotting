LATEX = pdflatex
BIBTEX = bibtex
FLAGS = -interaction=nonstopmode -halt-on-error

.PHONY: all clean auto

all: main.pdf 

define compile
	@echo "==> [$(1)] Pasada 1: generando .aux y referencias..."
	$(LATEX) $(FLAGS) $(1)
	@echo "==> [$(1)] BibTeX: procesando bibliografía..."
	$(BIBTEX) $(1) || true
	@echo "==> [$(1)] Pasada 2: resolviendo referencias bibliográficas..."
	$(LATEX) $(FLAGS) $(1)
	@echo "==> [$(1)] Pasada 3: finalizando referencias cruzadas..."
	$(LATEX) $(FLAGS) $(1)
endef

main.pdf: main.tex
	$(call compile,main)
	

auto:
	latexmk -pdf -pvc -interaction=nonstopmode -view=none main.tex

sync:
	git commit -am "sync" && git push

clean:
	rm -f main.pdf main.aux main.log main.bbl main.blg \
	      main.out main.toc main.fls main.fdb_latexmk main.synctex.gz \