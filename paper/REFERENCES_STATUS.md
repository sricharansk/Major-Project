# Bibliography verification status

Each entry was checked on 2026-10-20 from the development container by web search against the publisher's or
repository's own record (IJCAI proceedings, ACL Anthology, PMLR, NeurIPS proceedings, Springer, Project Euclid,
IEEE Xplore, ACM/CIKM anthology, arXiv, FHWA). `CHECKED` means title, authors, venue, year and (where given) pages
or identifier matched; a note records anything corrected or still open. Direct DOI/Crossref/arXiv API access was
denied by the container's network policy on 2026-10-20, so those checks used the publisher pages returned by search;
Crossref became reachable on 2026-10-21 and was used for the remaining open entry.

| key | identifier | type | status | note |
|---|---|---|---|---|
| li2018dcrnn | arXiv:1707.01926 | peer-reviewed (ICLR 2018) | CHECKED | arXiv record states "conference paper at ICLR 2018"; authors Li, Yu, Shahabi, Liu |
| yu2018stgcn | 10.24963/ijcai.2018/505 | peer-reviewed (IJCAI 2018) | CHECKED | pages 3634--3640 confirmed on ijcai.org |
| wu2019graphwavenet | 10.24963/ijcai.2019/264 | peer-reviewed (IJCAI 2019) | CHECKED | pages 1907--1913 confirmed on ijcai.org |
| brody2022gatv2 | arXiv:2105.14491 | peer-reviewed (ICLR 2022) | CHECKED | |
| vaswani2017attention | arXiv:1706.03762 | peer-reviewed (NeurIPS 2017) | CHECKED | added volume 30, pages 5998--6008 from the proceedings record |
| vovk2005algorithmic | 10.1007/b106715 | book (Springer 2005) | CHECKED | print ISBN 978-0-387-00152-4 |
| angelopoulos2021gentle | arXiv:2107.07511 | preprint | CHECKED | v6 revised 2022-12-07; still cited as preprint |
| barber2023beyond | 10.1214/23-AOS2276 | peer-reviewed (Ann. Statist. 51(2)) | CHECKED | pages 816--845, 2023 confirmed |
| xu2021enbpi | PMLR v139 | peer-reviewed (ICML 2021) | CHECKED | added pages 11559--11569 from proceedings.mlr.press |
| lundberg2017shap | arXiv:1705.07874 | peer-reviewed (NeurIPS 2017) | CHECKED | NeurIPS 30 proceedings record |
| lewis2020rag | arXiv:2005.11401 | peer-reviewed (NeurIPS 2020) | CHECKED | NeurIPS 33 per UCL Discovery record |
| reimers2019sbert | 10.18653/v1/D19-1410 | peer-reviewed (EMNLP-IJCNLP 2019) | CHECKED | pages 3982--3992 per ACL Anthology |
| johnson2019faiss | 10.1109/TBDATA.2019.2921572 | peer-reviewed (IEEE TBD 7(3)) | CHECKED | DOI confirmed on Crossref on 2026-10-21 (api.crossref.org/works/10.1109/TBDATA.2019.2921572): title, authors Johnson/Douze/Jegou, IEEE Transactions on Big Data 7(3), pages 535--547, issue date 2021-07-01 all match the bib entry |
| qwen2025qwen25 | arXiv:2412.15115 | preprint | CHECKED | v1 2024-12-19, v2 2025-01-03; bib year 2024 kept |
| lopez2018sumo | 10.1109/ITSC.2018.8569938 | peer-reviewed (ITSC 2018) | CHECKED | pages 2575--2582; SUMO's requested reference publication |
| rozemberczki2021pgt | 10.1145/3459637.3482014 | peer-reviewed (CIKM 2021) | CHECKED | pages 4564--4573 |
| fey2019pyg | arXiv:1903.02428 | workshop (ICLR 2019 RLGM) | CHECKED | |
| chen2016xgboost | 10.1145/2939672.2939785 | peer-reviewed (KDD 2016) | CHECKED | pages 785--794 |
| ke2017lightgbm | NeurIPS 2017 | peer-reviewed | CHECKED | NeurIPS 30 proceedings; no DOI |
| fhwa2008stm | FHWA-HOP-08-024 | government report (2008) | CHECKED | FHWA marks the 2008 edition as archived and superseded by the Signal Timing Manual, 2nd Edition (NCHRP 03-103); cited as the retrievable public-domain edition used in the corpus, with that caveat |
| mutcd2009 | FHWA MUTCD 2009 | government manual | CHECKED | 2009 Edition HTML at mutcd.fhwa.dot.gov; later editions exist, the 2009 text is what the corpus holds |
| nycdotspeeds | dataset i4gi-tjb9 | dataset | CHECKED (server-side audit) | identity and date range verified by `fetch.py audit` on 2026-10-20 |
| openmeteo | open-meteo.com | API | CHECKED (fetch log) | archive and historical-forecast endpoints returned HTTP 200 on 2026-10-20 |
| sumodocs_routing | SUMO v1_28_0 docs, Demand/Automatic_Routing.md | software documentation | CHECKED | fetched from the v1_28_0 tag on 2026-10-21; quoted behaviour: flows with from/to are routed automatically at insertion |
