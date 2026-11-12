# Pilot test results (KV-28)

Six volunteers each added one document to KnowledgeVault and then tried to find
it again by describing what it was about. The target was for at least 80% of
volunteers to complete both tasks.

**Result: 5 of 6 volunteers (83.3%) completed both tasks, so the target was met.**
That is the smallest number that clears 80%: one more failure would have meant
66.7%. Treat it as a narrow pass.

## How the sessions ran

- 15 minutes per volunteer, on the live site (API on AWS, app on CloudFront).
- Percival facilitated and read the script word for word. Durvank observed and
  filled in the log.
- Each volunteer got one printed target document (T1 to T6), a four-minute
  limit for each task, and no help during the tasks.
- The library held the 10 background documents plus the volunteer's upload, so
  search had other documents to rank against. Each upload was deleted afterwards.
- Task 2 counted as a pass only if the volunteer found the assigned document
  with a plain-language query inside four minutes.

## Results

| Volunteer | Task 1 (add) | Task 2 (find) | Result rank | Ease adding | Ease finding | Would use it |
|---|---|---|---|---|---|---|
| P1 | Pass, 2:18 | Pass, 1:42 | 1 | 5 | 5 | Yes |
| P2 | Pass, 3:06 | Pass, 2:34 | 2 | 4 | 4 | Maybe |
| P3 | Pass, 1:56 | Pass, 2:05 | 1 | 5 | 5 | Yes |
| P4 | Pass, 2:42 | **Fail**, timed out at 4:00 | none in top 5 | 4 | 2 | Maybe |
| P5 | Pass, 2:51 | Pass, 3:12 | 3 | 4 | 3 | Yes |
| P6 | Pass, 2:09 | Pass, 2:48 | 2 | 5 | 4 | Yes |

| Measure | Result |
|---|---|
| Both tasks completed | 5 of 6 (83.3%), target 80% |
| Task 1, adding a document | 6 of 6 |
| Task 2, finding it again | 5 of 6 |
| Average ease of adding (1 to 5) | 4.5 |
| Average ease of finding (1 to 5) | 3.8 |
| Would use it | 4 yes, 2 maybe, 0 no |
| Target document ranked first | 2 of 6 (P1, P3) |

## What we learned

1. **Search ranking for natural phrasing is the main weakness.** The right
   document was first for only two volunteers, second for two, third for one,
   and P4 never found theirs. P5 had to reword "bread bubbles" to mention
   sourdough before it worked. P6 expected the best match to always be first, so
   checked the next result too.
2. **Volunteers were not sure an upload had finished.** P1 expected a progress
   message, and P4 and P5 were unsure the app had finished until the document
   showed up.
3. **Adding a document was easy.** Everyone completed it, and three rated it 5.

## Follow-up tickets

These went into the backlog with the `pilot` label:

| Ticket | Follow-up |
|---|---|
| KV-47 | Search miss: P4's target did not appear in the top 5 |
| KV-48 | Improve ranking and show which passage matched |
| KV-49 | Show upload progress and confirmation |

## Limits

Six volunteers is a small sample. It shows where the rough edges are; it does
not say how search will perform with a large library. The target documents
were short one-page PDFs on everyday topics.

## Files

| File | What it is |
|---|---|
| [`observation-log.csv`](./observation-log.csv) | One row per volunteer: pass or fail, times, the exact query typed, result rank, ratings, problems seen |
| [`feedback-forms.md`](./feedback-forms.md) | The six completed feedback forms |
| [`facilitator-pack.md`](./facilitator-pack.md) | The script, session flow, ground rules and volunteer allocation |
| [`KnowledgeVault_6_Volunteer_Pilot_Pack.docx`](./KnowledgeVault_6_Volunteer_Pilot_Pack.docx) | The original pilot pack the files above were taken from |

Volunteers appear only as P1 to P6. No names, emails or personal files were
recorded.
