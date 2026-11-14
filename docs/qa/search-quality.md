# Search-quality test

Run on 2026-11-14 19:21 UTC against `https://3-13-43-176.sslip.io` with the real embedding model (model loaded: True).

The Project Charter's success criteria ask for a curated set of at least 20 documents and 15 plain-language queries, with a relevant source in the top 5 results for at least 80% of the queries, judged against an expected-source key written in advance.

**Result: 29 of 29 (100%) of queries had a relevant source in the top 5, against a target of 80%. The criterion is met.**

## How the test was set up

- **Library:** 24 documents in a fresh account, so nothing else could outrank them: 18 one-page PDFs (the 8 pilot targets and 10 background documents from `pilot/sample_docs/`) and 6 text notes (`eval/search_quality/notes/`). Topics range from cooking and health to Python, a meeting, and a travel plan.
- **Queries:** 29 plain-language queries, written before the first run and not changed afterwards (`eval/search_quality/queries.json`). 24 are paraphrases that avoid the document's own wording, 1 is a broad question where two documents count, and 4 are short keyword searches.
- **Pass rule:** a query passes if any expected document is among the first 5 results of the same `POST /search` call the app makes, with default settings (including the minimum score).
- **Negative queries:** 3 questions with no answer anywhere in the library. Search should return nothing.
- **Rerun:** `python eval/search_quality.py https://3-13-43-176.sslip.io` (see `eval/README.md`).

## Summary

| Measure | Result |
|---|---|
| Relevant source in the top 5 (the charter's measure) | 29 of 29 (100%) |
| Relevant source in the top 3 | 29 of 29 (100%) |
| Relevant source first | 29 of 29 (100%) |
| Mean reciprocal rank (1.0 = always first) | 1.00 |
| Negative queries that correctly returned nothing | 3 of 3 (100%) |

| Query type | Queries | Top 5 | First |
|---|---|---|---|
| paraphrase | 24 | 24 of 24 (100%) | 24 of 24 (100%) |
| broad | 1 | 1 of 1 (100%) | 1 of 1 (100%) |
| short | 4 | 4 of 4 (100%) | 4 of 4 (100%) |

## Every query

| # | Type | Query | Expected | Rank | Best result (score) |
|---|---|---|---|---|---|
| Q01 | paraphrase | my plant's leaves are yellowing and the soil never dries out | `B01_houseplant_care_basics.pdf` | 1 | B01_houseplant_care_basics.pdf (0.32) |
| Q02 | paraphrase | what can I do with eggshells and fruit peels instead of throwing them away | `T1_composting_at_home.pdf` | 1 | T1_composting_at_home.pdf (0.30) |
| Q03 | paraphrase | why do I feel worn out and sore the day after getting an injection | `T2_how_vaccines_work.pdf` | 1 | T2_how_vaccines_work.pdf (0.53) |
| Q04 | paraphrase | easy way to put savings in the stock market without choosing companies | `T3_index_funds_for_beginners.pdf` | 1 | T3_index_funds_for_beginners.pdf (0.35) |
| Q05 | paraphrase | how many weeks should I train before my first long-distance race | `T4_first_marathon_training.pdf` | 1 | T4_first_marathon_training.pdf (0.72) |
| Q06 | paraphrase | what is the stretchy network in dough that traps the gas | `T5_why_sourdough_rises.pdf` | 1 | T5_why_sourdough_rises.pdf (0.53) |
| Q07 | paraphrase | is pulling an all-nighter before an exam a good idea | `T6_sleep_and_memory.pdf` | 1 | T6_sleep_and_memory.pdf (0.56) |
| Q08 | paraphrase | what lights and lock do I need to commute on two wheels | `T7_bike_commuting.pdf` | 1 | T7_bike_commuting.pdf (0.30) |
| Q09 | paraphrase | does a roof full of panels still make power when it is overcast | `T8_how_solar_panels_work.pdf` | 1 | T8_how_solar_panels_work.pdf (0.51) |
| Q10 | paraphrase | how can I lower my heating bill this winter | `B10_home_energy_saving_tips.pdf` | 1 | B10_home_energy_saving_tips.pdf (0.55) |
| Q11 | paraphrase | what number do banks check before they approve a loan | `B07_understanding_credit_scores.pdf` | 1 | B07_understanding_credit_scores.pdf (0.33) |
| Q12 | paraphrase | quick dinner with noodles that takes twenty minutes | `B02_weeknight_pasta_and_rice.pdf` | 1 | B02_weeknight_pasta_and_rice.pdf (0.48) |
| Q13 | paraphrase | how do I write a one-line loop that filters a collection in Python | `B03_python_list_comprehensions.pdf` | 1 | B03_python_list_comprehensions.pdf (0.32) |
| Q14 | paraphrase | planning a drive through several parks without wasting days | `B04_national_parks_road_trip.pdf` | 1 | B04_national_parks_road_trip.pdf (0.76) |
| Q15 | paraphrase | what did we decide about onboarding at the planning meeting | `B05_meeting_notes_q3_planning.pdf` | 1 | B05_meeting_notes_q3_planning.pdf (0.53) |
| Q16 | paraphrase | bodyweight exercises I can do in my living room | `B06_home_workout_no_equipment.pdf` | 1 | B06_home_workout_no_equipment.pdf (0.48) |
| Q17 | paraphrase | how can I spot Jupiter and Orion without a telescope | `B08_beginners_guide_night_sky.pdf` | 1 | B08_beginners_guide_night_sky.pdf (0.68) |
| Q18 | paraphrase | best way to memorize vocabulary in a new language | `B09_learning_spanish_study_tips.pdf` | 1 | B09_learning_spanish_study_tips.pdf (0.57) |
| Q19 | paraphrase | why does my homemade brew taste bitter and how should I grind the beans | `N01_coffee_brewing_methods.txt` | 1 | N01_coffee_brewing_methods.txt (0.70) |
| Q20 | paraphrase | how does a model end up memorising its training data instead of learning | `N02_machine_learning_basics.txt` | 1 | N02_machine_learning_basics.txt (0.49) |
| Q21 | paraphrase | how should I answer a question about a time I failed at work | `N03_job_interview_preparation.txt` | 1 | N03_job_interview_preparation.txt (0.41) |
| Q22 | paraphrase | how do I get a blurry background in portraits | `N04_photography_exposure_basics.txt` | 1 | N04_photography_exposure_basics.txt (0.30) |
| Q23 | paraphrase | getting a new kitten used to the house | `N05_adopting_a_cat.txt` | 1 | N05_adopting_a_cat.txt (0.58) |
| Q24 | paraphrase | what to eat and see in Portugal's capital over a weekend | `N06_lisbon_weekend_itinerary.txt` | 1 | N06_lisbon_weekend_itinerary.txt (0.63) |
| Q25 | broad | ways to cut my electricity costs | `B10_home_energy_saving_tips.pdf` or `T8_how_solar_panels_work.pdf` | 1 | B10_home_energy_saving_tips.pdf (0.51) |
| Q26 | short | sourdough starter | `T5_why_sourdough_rises.pdf` | 1 | T5_why_sourdough_rises.pdf (0.50) |
| Q27 | short | index fund | `T3_index_funds_for_beginners.pdf` | 1 | T3_index_funds_for_beginners.pdf (0.69) |
| Q28 | short | learn Spanish | `B09_learning_spanish_study_tips.pdf` | 1 | B09_learning_spanish_study_tips.pdf (0.66) |
| Q29 | short | compost | `T1_composting_at_home.pdf` | 1 | T1_composting_at_home.pdf (0.50) |

## Misses

None. Every query had a relevant source in the top 5.

## Negative queries (nothing in the library should match)

| # | Query | Results returned | Best result (score) |
|---|---|---|---|
| N1 | causes of the French Revolution | 0 | - |
| N2 | how to fix a leaking kitchen faucet | 0 | - |
| N3 | how to knit a sweater | 0 | - |

## Limits

- The library is small (24 short documents), so every query has few rivals. The result shows that meaning-based search works on this set; it does not predict performance on thousands of documents.
- The queries were written by the team, who know what the documents say. The pilot volunteers' own wording (`pilot/results/`) is the more independent evidence for how real users search.
- Scores depend on the embedding model and the minimum-score setting, so a rerun after changing either should be compared with this file.
