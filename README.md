# global-company-index

Builds an open index of companies worldwide from public data only:

* **Wikidata** (CC0): businesses with an industry, products, a website or a descriptive summary;
  dissolved / defunct companies are excluded
* **US FDA openFDA** (public domain): drug-ingredient labelers and medical-device manufacturers

Each company gets a short profile (name, description, products, industry, country, website)
and a `bge-small-en-v1.5` embedding for semantic search. Output is attached to the workflow
run as an artifact. Run it from the Actions tab (`build-index`).
