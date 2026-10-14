# Sources and third-party material

No third-party code is bundled. The runtime is CPython standard library only.

## The service corpus (`data/service.json`)

The twelve service entries E01-E12 that `search_service_info` returns
paraphrase public service and product guidance. (The configurations also embed
two benchmark-policy entries, B01 and B02, which cite only the benchmark's own
rules (source B1); search can return them too, so it has 14 cited entries in
all.) The corpus cites its sources by ID; the
source records carry the title, the kind of document and neutral custody
hashes of the citation record. No source text, page image, PDF or URL is
reproduced, and no source document is shipped.

| ID | Title | Kind |
|---|---|---|
| M | A printed service manual (not redistributed) | public manual reproduction, cited by page number only |
| S1 | Cylinder-head service instructions | commercial service article |
| S2 | Fastener tightening instruction | fastener-manufacturer sheet on a public supplier mirror |
| S3 | MLS gasket installation and surface-finish guidance | gasket-manufacturer technical guidance |
| S4 | Gasket surface preparation guidance | gasket-manufacturer technical guidance |
| S5 | General cylinder-head fastener reuse guidance | fastener-manufacturer guidance |
| S6 | Replacement gasket product listing | gasket-manufacturer catalog |
| S7, S8 | Historical citation records | citation metadata; the analyst-estimate basis of the labor table cites S7 |
| B1 | Study design v2 and Amendment 1 benchmark policy | the benchmark's own rules |

Applicability of any source to a specific engine is not claimed. Where
sources disagree (30/73 N m in S2 against 30/72 N m in S1; several complete
crank turns for the timing recheck) the corpus says so and names the benchmark
choice.

## What the published corpus withholds

The corpus shipped here is the one embedded in every published run record
(the configurations are byte-identical to those records). Compared with the
research corpus it withholds, but does not otherwise change:

- for source M, the manual's locator digest, locator-record digest and table
  digest; its entries keep the page numbers and the specific values the
  upstream review read from those pages, with the citation, and nothing else
  of the manual;
- for S7 and S8, the private document digests and proposal-record digests;
  their qualification sentences say the digests are withheld.

The labor table `data/labor-v2.json` cites S7 by ID only, and
`data/human-time-policy-v3.json` is derived from it. Every duration, rule and
entry ID is unchanged. Does a checkpoint depend on the withheld digests? No:
the twelve checkpoints are computed by `hgj/checkpoints.py` from the action
journal and the final state, and the only checkpoint that reads the corpus
(CP01, service lookup before head tightening) checks which entry IDs were
retrieved.

The removal-policy input (`removal-policy/job-checklists.json`) cited the
study design by a machine-local shared-folder path in 625 basis records; the
path was replaced by the neutral label `benchmark-policy/<document>`. See
`removal-policy/README.md`.

## Engine

The engine is a real 1990s 1.6 L SOHC inline-four. The geometry, part
identities and service positions in the configurations are the benchmark's
own labelled model of it. Manufacturer and model names are not used in this
software.

ToolsEnabled is not affiliated with or endorsed by Anthropic, OpenAI or any other AI provider.
