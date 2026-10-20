$pdflatex = 'pdflatex -shell-escape';

# glossaries: que latexmk corra makeglossaries cuando cambian los acronimos
# (.acn -> .acr) o el glosario (.glo -> .gls). Fragmento recomendado por el
# propio paquete glossaries.
add_cus_dep('glo', 'gls', 0, 'run_makeglossaries');
add_cus_dep('acn', 'acr', 0, 'run_makeglossaries');
sub run_makeglossaries {
  if ( $silent ) { system "makeglossaries -q '$_[0]'"; }
  else { system "makeglossaries '$_[0]'"; };
}
push @generated_exts, 'glo', 'gls', 'glg', 'acn', 'acr', 'alg';
$clean_ext .= ' %R.ist %R.xdy';