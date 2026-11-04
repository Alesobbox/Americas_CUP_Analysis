# Research review for the three forecasting outputs

Research checked: 15 October 2026; policy revised after the user's engineering/statistical review. This is a design review, not trained-model results. Read [the execution plan](probability_execution_plan.md) and [point-by-point resolution](forecasting_review_resolution.md) for the binding MVP scope and corrected mathematical specifications.

## Conclusion and changes to the previous proposal

Build a common Monte Carlo engine with interchangeable, tested statistical components. The leading generative candidate is an empirical, hierarchical next-gate/leg-time simulator, including a reviewed severe-loss mixture candidate. Its mandatory benchmark is regularized field-aware logit/Plackett–Luce. Optional shallow boosting follows a measured core. SVR/HMM and all sequence/foundation work are post-MVP research, not shipping requirements. Do not select a winner before evaluating complete forecasts.

The literature supports this comparison; it does not establish that a large neural network, a foundation model, or a detailed simulator will be best on this archive. Dense telemetry is useful for learning local dynamics, but it does not turn 28 sessions on nine dates into millions of independent race outcomes.

The earlier practice weight of 0.25, fixed AC40-to-AC75 coefficient of 0.5, and particular AC75 discrepancy variance had no empirical justification. They are removed as production defaults. Noncompletion assumptions, transfer assumptions, and Monte Carlo numerical error must be reported separately from evidence about predictive accuracy.

## How to read the evidence

Entries distinguish what a source studied from the application proposed here. A paper's reported improvement belongs to its own dataset and evaluation. No quoted improvement below is an expected improvement for AC40 or AC75 forecasts. Primary manuscripts, proceedings, author/institutional repositories, and official model documentation are used. Where only an abstract was inspected, this is stated.

## 1. Direct sailing and adjacent watersports research

### R01 — Joint yacht-race simulation

Philpott, Henderson and Teirney (2004), *A Simulation Model for Predicting Yacht Match Race Outcomes*, Operations Research 52(1), 1–16. [Author manuscript](https://people.orie.cornell.edu/shane/pubs/AmCup.pdf).

The model simulates both yachts together, with dynamic performance, hidden-Markov wind, simple tactical rules, and interaction effects. Its experiments show why spatial wind correlation matters to race-win estimates. This directly supports a correlated Monte Carlo architecture. However, the authors have velocity-prediction and hydrodynamic/aerodynamic inputs absent here, and study IACC match races. Their numerical simulation precision is not evidence of empirical AC40 probability calibration. Reuse the architecture principles, not their coefficients or physical model.

### R02 — Wind forecasting plus tactical decisions

Tagliaferri and Viola (2017), *A real-time strategy-decision program for sailing yacht races*, Ocean Engineering 134, 129–139. [Author manuscript](https://www.pure.ed.ac.uk/ws/portalfiles/portal/33415796/Tagliaferri_Viola_Ocean_Engineering_2017.pdf).

Combines neural wind forecasts, dynamic programming, opponent penalties, and risk preferences using AC34 wind data. This supports treating weather and future decisions as separate components. Routing gains under specified dynamics do not establish calibrated winner probabilities. The experimental interaction parameters and detailed tactical optimization are unsuitable initial dependencies for this repository.

### R03 — Small supervised models for sailing wind

Tagliaferri, Viola and Flay (2015), *Wind direction forecasting with artificial neural networks and support vector machines*, Ocean Engineering 97, 65–73. [Institutional record](https://eprints.ncl.ac.uk/214057), [publisher](https://www.sciencedirect.com/science/article/pii/S0029801814004831).

The study compares ANN and SVR forecasts using America's Cup wind data. The abstract reports a favorable SVR comparison against an ANN ensemble. This motivates a low-capacity SVR/regularized autoregression benchmark rather than assuming deep learning is required. Course-average direction is not a resolved local wind field; compass angles also require circular/vector treatment.

### R04 — Supervised and unsupervised yacht-performance learning

Byrne et al. (2022), *Using Machine Learning to Model Yacht Performance*, Journal of Sailing Technology 7, 104–119. [Journal record](https://repository.tudelft.nl/record/uuid:83ffbf0f-b023-4bd0-9b08-cd94ddfde11e), [inspected 2021 conference manuscript](https://journals.ed.ac.uk/MARINE2021/article/download/6837/9034/22213).

Studies clustering, neural networks, random forests, SVMs, and physics-based corrections on one TP52 over eight days. It supports empirical performance models and regime/quality analysis. Important limitation: the inspected conference version uses random point splits for performance regression, although its racing-mode classification also uses day holdouts. Its large reported regression improvements cannot be treated as evidence of future-race forecast accuracy. It also has sensor channels unavailable here.

### R05 — Regularized, sailing-informed performance surfaces

Olsson and Marimon Giovannetti (2026), *Physics-Guided Machine Learning for Performance Modelling of the Nacra 17 Class*, Journal of Sailing Technology 11, 238–260. [Publisher](https://onepetro.org/JST/article/11/01/238/801669/Physics-Guided-Machine-Learning-for-Performance?searchresult=1), [DOI](https://doi.org/10.5957/jst/2026.11.1.238).

The primary publisher abstract describes a ridge model with physics-motivated wind/angular basis terms and a residual-noise surface, evaluated across crews and regattas. This is a useful small-model design lead. Evidence here is abstract-level: the complete paper was not independently inspected. Do not transplant its coefficients, its reported improvement, or all its basis terms. The execution plan independently tests a compact, regularized performance response using available AC40 features.

### R06 — Learning polars from real observations

Dannenberg, Schüler and Schürmann (2022), *A Data Processing Framework for Polar Performance Diagrams*, Applied Sciences 12, 3085. [Publisher](https://www.mdpi.com/2076-3417/12/6/3085), [author manuscript](https://www.mathematik.uni-rostock.de/storages/uni-rostock/Alle_MNF/Mathematik/Struktur/Lehrstuehle/Geometrie/Dateien/SoftwareForPolarPerformanceDiagrams.pdf).

Provides a modular empirical-performance framework. Relevant distinctions include environmental influences and idealized performance versus observations. With SOG/COG and no measured current/leeway, this project can fit an empirical ground-relative performance response; it cannot identify a clean water-relative physical polar. This limits claims about changed-current or changed-wave scenarios.

### R07 — Tactical games and risk objectives

Cacace, Ferretti and Festa (2020), *Stochastic hybrid differential games and match race problems*. [Author preprint](https://arxiv.org/abs/1906.10968). Wang et al. (2023), *Risk-aware stochastic control of a sailboat*. [Preprint](https://arxiv.org/abs/2309.13436).

These establish useful control formulations under specified dynamics and illustrate that minimum expected time and maximum success probability can imply different policies. They do not identify actual crew tactics from this archive. Reinforcement learning, adversarial tactical optimization, and a physical digital twin are therefore deferred research, not v1 commitments.

### R08 — Unsupervised patterns in adjacent watersports

Estreich et al. (2025), *An analysis of pacing profiles in sprint kayak racing using functional principal components and hidden Markov models*. [Primary article](https://pmc.ncbi.nlm.nih.gov/articles/PMC12221036/).

Functional PCA and HMMs provide a watersports example of descriptive latent structure, including career-level pacing-profile changes rather than within-race sailing states. This supports testing compact representations, not assuming a sailing regime model is validated. Full-race profiles are retrospective, not valid time-t features. A discovered cluster does not establish a causal mechanism, a retirement, or a winner label.

## 2. Rankings, strength, and supervised prediction

### R09 — Plackett–Luce and partial rankings

Turner et al. (2020), *Modelling rankings in R: the PlackettLuce package*. [Primary paper](https://link.springer.com/article/10.1007/s00180-020-00959-3).

Provides a coherent ranking framework with partial orders, ties, and regularization. It is a strong pre-race and conditional-state benchmark. Its independence-of-irrelevant-alternatives structure may miss tactical interactions. An incomplete recording is not automatically a valid partial ranking or a last-place outcome; only established comparisons may enter the likelihood.

### R10 — Dynamic strengths and rating uncertainty

Cattelan, Varin and Firth (2013), *Dynamic Bradley–Terry modelling of sports tournaments*. [Primary paper](https://doi.org/10.1111/j.1467-9876.2012.01046.x). Herbrich, Minka and Graepel (2006), *TrueSkill: A Bayesian Skill Rating System*. [Author manuscript](https://www.microsoft.com/en-us/research/wp-content/uploads/2007/01/NIPS2006_0688.pdf). Glickman (1999), *Parameter estimation in large dynamic paired comparison experiments*. [Author paper](https://www.glicko.net/research/glicko.pdf).

Support explicit ability uncertainty and, with suitable evidence, ability evolution. TrueSkill accommodates multiplayer results; Bradley–Terry is naturally pairwise. None supplies weather/course dynamics. Nine dates do not identify unconstrained daily team drift, and converting one fleet result into many pairwise rows does not produce independent races. Start with static, pooled strength and test tightly constrained updates.

### R11 — Sport-specific remaining-contest models

Robberechts, Van Haaren and Davis (2021), *A Bayesian Approach to In-Game Win Probability in Soccer*. [Author manuscript](https://www.janvanhaaren.be/assets/papers/kdd-2021-win-probability.pdf).

Models the remainder of a contest using domain structure and compares with generic classifiers. This is a close methodological analogue for remaining-course simulation and terminal behavior. Its soccer event process, large dataset, and reported results cannot be transferred to sailing. It supports the experiment, not a predeclared generative-model victory.

### R12 — Tree boosting and the tabular/deep comparison

Prokhorenkova et al. (2018), *CatBoost: unbiased boosting with categorical features*. [Primary paper](https://proceedings.neurips.cc/paper/7898-catboost-unbiased-boosting-with-categorical-features.pdf). Grinsztajn, Oyallon and Varoquaux (2022), *Why do tree-based models still outperform deep learning on typical tabular data?* [Proceedings](https://proceedings.neurips.cc/paper_files/paper/2022/hash/0378c7692da36807bdec87ab043cdadc-Abstract-Datasets_and_Benchmarks.html).

Support benchmarking shallow boosted trees before large tabular neural networks. CatBoost's ordered processing addresses particular target-leakage mechanisms; it does not fix future data introduced by the dataset or preprocessing. These studies do not prove trees are best for sailing. Test a small boosted residual correction with a strict race/day split and keep identity/strength inference in its regularized layer.

## 3. Deep learning and pretrained sequence models

### R13 — TimesFM

[Original ICML paper](https://arxiv.org/abs/2310.10688), [Google's TimesFM-3 explanation, 31 August 2026](https://research.google/blog/timesfm-3-a-zero-shot-foundation-model-for-multivariate-forecasting/), [official repository](https://github.com/google-research/timesfm).

TimesFM 3 adds native multivariate and historical/known-future covariates. TimesFM 2.5 has a univariate core and an XReg workflow. Both are candidates for short-horizon performance residuals. Their exposed quantiles do not specify a full joint boat-by-time trajectory distribution. Public general-domain benchmarks establish no sailing accuracy. Downloaded 3.0 weights are restricted to non-commercial, non-production use; versions through 2.5 retain Apache-2.0 weights. A model released after a historical forecast date also cannot demonstrate original-date operational availability.

### R14 — Chronos-2 and Chronos-Bolt

Ansari et al., *Chronos-2: From Univariate to Universal Forecasting*. [Paper](https://arxiv.org/abs/2510.15821), [official Apache-2.0 weight card](https://huggingface.co/amazon/chronos-2). [Chronos-Bolt official model card](https://huggingface.co/amazon/chronos-bolt-small).

Chronos-2 uses grouped information for multivariate/covariate forecasting and is the default locally deployable multivariate foundation-model experiment. Bolt is an inexpensive univariate comparator. Quantile outputs still need an explicitly tested dependence sampler. Zero-shot forecasting reduces the need for local weight training; it does not remove domain shift, label verification, or probability calibration requirements.

### R15 — Moirai

Woo et al. (2024), *Unified Training of Universal Time Series Forecasting Transformers*. [Paper](https://arxiv.org/abs/2402.02592), [official Moirai 1.1 weight card](https://huggingface.co/Salesforce/moirai-1.1-R-small).

Any-variate forecasting and distributional outputs are relevant alternatives. Code licensing must not be confused with weight licensing: the inspected weights have noncommercial restrictions. Keep this an optional research comparator, not an initial production dependency. Distributional output alone does not establish realistic dependence across boats and forecast times.

### R16 — Compact trained sequence models

Salinas et al., *DeepAR: Probabilistic Forecasting with Autoregressive Recurrent Networks*. [Paper](https://arxiv.org/abs/1704.04110). Bai, Kolter and Koltun (2018), *An Empirical Evaluation of Generic Convolutional and Recurrent Networks for Sequence Modeling*. [Paper](https://arxiv.org/abs/1803.01271). Lim et al., *Temporal Fusion Transformers for Interpretable Multi-horizon Time Series Forecasting*. [Paper](https://arxiv.org/abs/1912.09363).

DeepAR motivates probabilistic autoregressive traces, and TCN research supports testing causal convolutions instead of assuming recurrent models are preferable. TFT illustrates static, observed, and known-future inputs. Test one small GRU and one small TCN with fixed settings. Defer a full TFT/large-transformer search. Within-series autoregression does not by itself establish cross-boat dependence.

### R17 — Self-supervised representations

Yue et al. (2022), *TS2Vec: Towards Universal Representation of Time Series*. [Paper](https://arxiv.org/abs/2106.10466).

Unlabeled telemetry can support reusable representations. This is a gated experiment after interpretable features and simple models. Train representations only inside the past training fold, then test a simple downstream predictor. An embedding cannot supply missing finishing labels or target-class AC75 validation.

## 4. Dependence, evaluation, and transfer

### R18 — Reconstructing correlated forecast paths

Clark et al. (2004), *The Schaake Shuffle*. [USGS primary record](https://pubs.usgs.gov/publication/70027101). Schefzik, Thorarinsdottir and Gneiting (2013), *Uncertainty Quantification in Complex Simulation Models Using Ensemble Copula Coupling*. [Paper](https://arxiv.org/abs/1302.7149). Salinas et al. (2019), *High-dimensional multivariate forecasting with low-rank Gaussian Copula Processes*. [Paper](https://arxiv.org/abs/1910.03002).

These motivate separating marginal forecasts from cross-variable/time dependence. Start with synchronized residual blocks and small shared factors. Neither independent quantile draws nor one common quantile for every boat is acceptable. Historical dependence can change with conditions; block matching and factor shrinkage require validation. A large free covariance/copula model is inappropriate for this archive.

### R19 — Proper probability and trajectory scores

Gneiting and Raftery (2007), *Strictly Proper Scoring Rules, Prediction, and Estimation*. [Author manuscript](https://sites.stat.washington.edu/people/raftery/Research/PDF/Gneiting2007jasa.pdf). Scheuerer and Hamill (2015), *Variogram-Based Proper Scoring Rules for Probabilistic Forecasts of Multivariate Quantities*. [NOAA primary record](https://repository.library.noaa.gov/view/noaa/22327/).

Use winner log loss and Brier score, place-distribution ranked probability score, and squared error for expected place. Squared error targets the mean; MAE is secondary. For trajectories, use marginal CRPS plus energy/variogram diagnostics and cross-boat gap errors. The variogram paper is especially relevant because marginal scores and even energy scores can miss dependence errors. Top-one accuracy alone does not assess probability quality.

### R20 — Selection, calibration, and dependence-aware evaluation

Cawley and Talbot (2010), *On Over-fitting in Model Selection and Subsequent Selection Bias in Performance Evaluation*. [Paper](https://www.jmlr.org/papers/v11/cawley10a.html). Guo et al. (2017), *On Calibration of Modern Neural Networks*. [Proceedings](https://proceedings.mlr.press/v70/guo17a.html). Roberts et al. (2017), *Cross-validation strategies for data with temporal, spatial, hierarchical, or phylogenetic structure*. [Primary paper](https://onlinelibrary.wiley.com/doi/full/10.1111/ecog.02881).

Support predeclared candidates, structured splits, and cautious calibration. Few days make a large model search particularly vulnerable to selection noise. Temperature scaling is a candidate, not guaranteed calibration for sailing. Use identity calibration until enough earlier out-of-fold competitive dates exist. No random frame split, flexible isotonic fit on a few races, or claimed 95% calibration guarantee is justified.

### R21 — Limits of distribution transfer and conformal promises

Ben-David et al. (2010), *A theory of learning from different domains*. [Primary paper](https://link.springer.com/article/10.1007/s10994-009-5152-4). Ben-David et al. (2010), *Impossibility Theorems for Domain Adaptation*. [Proceedings](https://proceedings.mlr.press/v9/david10a.html). Barber et al. (2023), *Conformal prediction beyond exchangeability*. [Author manuscript](https://www.stat.cmu.edu/~ryantibs/papers/nexcp.pdf).

Source-domain success alone does not identify target-domain performance. AC40-to-AC75 transfer needs assumptions about shared crew skill, changed crew roles, and independent boat/system capability. Conformal methods do not remove that requirement or provide automatic coverage under this class shift. Publish explicit transfer scenarios and sensitivity; update with actual AC75 evidence. Do not claim a learned transfer coefficient from AC40-only observations.

## 5. Operational sources

Additional primary background for revision 2:

- **R22 — Missing measurements:** [Sinopoli et al., Kalman filtering with intermittent observations](https://people.eecs.berkeley.edu/~jordan/papers/sinopoli-etal.pdf). Supports covariance propagation under intermittent data, not a validated 60-second straight-line sailing bridge. The annex specifies its motion/noise model and empirical certification separately.
- **R23 — Mixture interpretation:** [Gormley and Frühwirth-Schnatter, Mixtures of Experts Models](https://arxiv.org/abs/1806.08200). Supports conditional component models and the need for identification. It establishes neither foil-state labels nor sailing speed/delay thresholds.
- **R24 — Diffusion baseline:** [Stern, A Brownian Motion Model for the Progress of Sports Scores](https://www.stat.berkeley.edu/~aldous/157/Papers/stern.pdf). Motivates a remaining-time signal/noise benchmark. Applying it to spatial first-passage racing is an explicitly tested analogy.
- [uv lock/sync documentation](https://docs.astral.sh/uv/concepts/projects/sync/) and [dependency-resolution rules](https://docs.astral.sh/uv/concepts/resolution/): locked core extras and separately isolated research where dependency constraints conflict. Locking does not require installing Torch into replay ingestion.

- [Official AC38 noticeboard](https://ac38noticeboard.acofficials.org/): governing document versions and precedence.
- [AC38 Protocol incorporating amendments 1–10](https://drive.google.com/file/d/1MZZN-TJlXUkaqTNxCje8RupzAjBP4vvL/view), [LVC/Match Conditions v0](https://drive.google.com/file/d/1biI3_zCSaLrRiM4nwkhKpaBnMraS5KiP/view), [RRSAC v5.02](https://drive.google.com/file/d/1I21drErgKm4OuYCcGb3D9uv7_UYG4jwj/view): pin exact copies and hashes during implementation; check subsequent instructions before publication.
- [Official 2027 format explanation](https://www.americascup.com/news/4148_FLEET-RACING-AC75-s-TO-KICK-START-THE-LOUIS-VUITTON-CUP): fleet stage, round robins, repechage, semifinals and finals. Governing documents override the article.
- [Official teams](https://www.americascup.com/teams) and [AC40/AC75 preparation debrief](https://www.americascup.com/news/4379_LEARNINGS-FROM-NAPLES-TEAM-BY-TEAM): identity and transfer context, not numeric ability labels.
- [Open-Meteo archived individual runs](https://open-meteo.com/en/docs/single-runs-api), [ensembles](https://open-meteo.com/en/docs/ensemble-api), [marine data](https://open-meteo.com/en/docs/marine-weather-api): weather acquisition capabilities. Initialization, publication availability and valid time must remain distinct.

## Research decisions

| Family | Initial role | Decision |
| --- | --- | --- |
| Hierarchical logit / Plackett–Luce / small GAM | Required coherent ranking benchmark | Implement first; eligible fallback for all three outputs through Monte Carlo order sampling. |
| Empirical positive next-gate/leg-time model | Leading generative race candidate | Implement with partial pooling and correlated residuals; must earn promotion. |
| Shallow CatBoost / quantile boosting | Optional nonlinear residual candidate | Test after the core; not a prerequisite to ship. |
| HMM / clustering / SVR | Post-MVP regimes, representation and residual research | First use causal kinematic summaries; add only with demonstrated value. |
| Chronos-2 / TimesFM 2.5 | Post-MVP frozen short-horizon candidate | Test incremental value before fine-tuning; never delay the core. |
| TimesFM 3 / Moirai | Optional research comparison | Respect weight licenses; not an automatic production dependency. |
| Small GRU / causal TCN | Post-MVP trained sequence experiment | Fixed small architectures; three seeds; no broad search or MVP dependency. |
| Self-supervised representation / LoRA | Conditional follow-up | Only after a demonstrated need and earlier model value. |
| Large scratch neural network / GNN / RL / full VPP twin | Future research | Defer until data, missing inputs, or failure analysis justify it. |

The implementation is successful when these methods are compared reproducibly and the released model is the best-supported coherent forecast available. Success does not require a complex model to defeat the baseline.
