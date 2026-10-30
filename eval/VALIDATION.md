# Validation against real ad outcomes

Written **before** any of these ads was run through Culture Check (2026-10-29).
The predictions below are fixed; the results get appended underneath, whatever
they are. Nothing in the pipeline is tuned on these ads.

## What Culture Check claims, and what it does not

It measures whether a video's **cultural cues** (music, people, brands, places,
styles, settings) are things a given audience over-indexes on, according to
Qloo. It does not judge the message, the joke, the tone, or whether an ad is
offensive. A test it should pass is one where an audience liked or rejected an
ad *for who and what is in it*; a test it should fail, and we say so, is one
decided by the message.

The headline number per ad is the **age gap**: Qloo fit for under-25s minus fit
for 55+, from the same report (one read of the video, two audiences).

## Test 1: same Super Bowl, different generations (HarrisX Ad Index 2026)

Source: [HarrisX Ad Index, Super Bowl LX](https://www.harrisx.com/ad-index):
9,707 US adults, each ad rated by 500+ respondents on eight measures.

- Lay's "Last Harvest": #1 overall (93.2), top with Millennials, Gen X and
  Boomers; only #4 with Gen Z.
- Pringles "Pringleleo" (Sabrina Carpenter): the clear #1 with Gen Z (94.8),
  #22 overall (78.5).
- Also named as Gen Z favourites ranked outside the overall top 15: the NFL's
  "Champion", Bud Light, Nerds, Hellmann's.
- Overall top five: Lay's, Ring "Be A Hero In Your Neighborhood", Pepsi
  "The Choice", Google "New Home", Blue Square Alliance "Sticky Note".

**Predictions**
- P1. Pringles' age gap is larger (more youth-leaning) than Lay's.
- P2. The Gen Z favourites (Pringles, NFL, Bud Light, Nerds, Hellmann's) have a
  larger mean age gap than the overall leaders (Lay's, Ring, Google).

## Test 2: a brand that walked away from its buyers (Jaguar, 2024)

Jaguar's "Copy Nothing" film (Nov 2024) shows models and fashion and no car.
Coverage reports a backlash from its existing, older and affluent buyers and
falling sales; a randomised test by Grow Progress (1,200+ US adults earning
$75k+) found a conventional Jaguar E-PACE ad outperformed it
([Grow Progress](https://growprogress.ai/insight/jaguar-rebrand); vendor study,
treated with caution).

**Predictions**, for men 45-54 (the core luxury-car buyer):
- P3. "Copy Nothing" scores lower than the E-PACE ad.
- P4. "Copy Nothing" leans young: its age gap is positive.

## Test 3: a failure Culture Check should NOT catch (Pepsi, 2017)

Pepsi "Live for Now" (Kendall Jenner) targeted millennials and was pulled within
a day; YouGov BrandIndex shows millennial purchase consideration falling 27% to
24% ([YouGov](https://today.yougov.com/news/2018/04/17/one-year-after-jenner-ad-crisis-pepsi-recovers/)).
It failed on its message (protest trivialised), not on its cues.

**Prediction**
- P5. Culture Check rates it as fitting 25-29s. This is a stated limitation,
  reported as one.

## Method

- Each video goes through the deployed pipeline unchanged, no soundtrack given
  by hand (what is heard comes from the transcript).
- Each report is viewed for under 25, 55+, and the audience named in its test.
- The model-alone baseline is recorded beside Qloo for every one.

## Results

### Run 1: blind (2026-10-29), the pipeline exactly as it was when the predictions were written

Videos: seven official brand uploads; Pringles, Bud Light "Keg", Jaguar "Copy
Nothing" and Pepsi from ad-archive channels, since the brands no longer host them.
Pepsi was run whole (168 s). Fit is the weighted mean over cues Qloo could score,
from −1 to 1. "LLM alone" is the same model given the same cues and the same
audience, with no Qloo.

| ad | group | named audience | Qloo fit | LLM alone | Qloo gap (<25 − 55+) | LLM-alone gap | cues scored |
|---|---|---|---|---|---|---|---|
| Lay's · Last Harvest | leader | 35-44 | +0.06 | +0.39 | −0.06 | −0.78 | 12/17 |
| Ring · Be A Hero | leader | 35-44 | −0.21 | +0.72 | −0.08 | −0.58 | 6/14 |
| Google · New Home | leader | 35-44 | −0.31 | +0.72 | −0.22 | −0.07 | 13/18 |
| Pringles · Pringleleo | genz | under 25 | +0.13 | +0.21 | +0.23 | −0.09 | 13/25 |
| NFL · Champion | genz | under 25 | +0.03 | +0.66 | −0.02 | +0.32 | 9/13 |
| Bud Light · Keg | genz | under 25 | −0.10 | +0.36 | −0.03 | +0.07 | 17/22 |
| Nerds | genz | under 25 | +0.08 | +0.78 | +0.21 | +0.52 | 13/21 |
| Hellmann's | genz | under 25 | −0.31 | +0.36 | −0.56 | −0.29 | 11/13 |
| Jaguar · Copy Nothing | jaguar | men 45-54 | −0.24 | −0.03 | +0.02 | +0.16 | 14/17 |
| Jaguar · E-PACE | jaguar | men 45-54 | −0.07 | +0.48 | +0.11 | +0.04 | 10/14 |
| Pepsi · Live for Now | pepsi | 25-29 | −0.01 | +0.70 | +0.20 | +0.30 | 25/36 |

| prediction | Qloo | LLM alone |
|---|---|---|
| P1 Pringles leans younger than Lay's | PASS (+0.23 vs −0.06) | pass (−0.09 vs −0.78) |
| P2 Gen Z favourites lean younger than leaders | PASS, weakly (−0.03 vs −0.12) | pass (+0.11 vs −0.48) |
| P3 Copy Nothing below E-PACE, men 45-54 | PASS (−0.24 vs −0.07) | pass (−0.03 vs +0.48) |
| P4 Copy Nothing leans young | nominal PASS (+0.02: no real lean) | (+0.16) |
| P5 Pepsi rated as fitting 25-29 | FAIL: neutral (−0.01) | (+0.70) |

**What this run shows, without spin**

- The predictions mostly held, but the LLM alone got the same directions, often by
  larger margins. On this set the taste graph did not beat stereotype on direction.
- What the LLM alone did not do is say anything is off: it rated the named audience
  positively for 10 of 11 ads (+0.21 to +0.78, Copy Nothing −0.03). Qloo spread them
  from −0.31 to +0.13.
- Hellmann's, a Gen Z favourite, came out strongly old on both.
- **Cause 1: the people were missing.** The frame question never identifies anyone
  from their face, so the cast of a celebrity ad never became cues: Sabrina Carpenter
  (Pringles); Andy Samberg, Elle Fanning and Neil Diamond (Hellmann's); Post Malone,
  Peyton Manning and Shane Gillis (Bud Light). Those are the cues a Super Bowl ad is
  built on, and the ones Qloo holds the best data for.
- **Cause 2: generic tags.** A colour or a word like "Fashion", "Art", "Studio" or
  "Modeling" matched a Qloo tag with a strong profile and moved the score:
  "glossy red manicure" → *Red* (−0.85), "runway walk" → *Modeling* (−0.81). Copy
  Nothing's −0.24 rests largely on these.
- Coverage: 43-77% of cues had Qloo audience data.

### Run 2: not blind, after two fixes made because of run 1 (2026-10-29)

**Fixes.**
- A "Who's in it" input. Each name becomes a person or artist cue.
- No colour tags, and no tags so broad they say nothing about taste.

**Names given.** Only the names in each ad's own title or press: Sabrina Carpenter;
Post Malone, Peyton Manning and Shane Gillis; Andy Cohen; Andy Samberg, Elle
Fanning and Neil Diamond; Kendall Jenner, with Skip Marley's "Lions" as the music.

**Method.** Every ad was read again from the video, so the cues are a new draw.

| ad | Qloo fit | Qloo gap | run 1 gap |
|---|---|---|---|
| Lay's | −0.37 | −0.01 | −0.06 |
| Ring | −0.23 | −0.47 | −0.08 |
| Google | −0.17 | +0.06 | −0.22 |
| Pringles | +0.12 | −0.01 | +0.23 |
| NFL Champion | −0.29 | −0.17 | −0.02 |
| Bud Light | +0.04 | +0.06 | −0.03 |
| Nerds | −0.02 | −0.15 | +0.21 |
| Hellmann's | −0.04 | −0.41 | −0.56 |
| Copy Nothing | −0.44 | +0.01 | +0.02 |
| E-PACE | −0.08 | +0.66 | +0.11 |
| Pepsi | −0.18 | −0.08 | +0.20 |

**What it shows.**
- **Worse, not better.**
  - Pairs ranked right (Gen Z favourite more youth-leaning than a leader): 8/15,
    down from 12/15. Chance is 7.5.
  - P1 is a tie.
  - P3 still holds.
- **The noise is as large as the signal.** The same ad's gap moved by up to 0.55
  between runs. The cue list changes with every reading of the video, and the
  overall score is a flat mean over 10-20 cues.
- **The strong cues are right.**
  - Sabrina Carpenter: +0.88 for under-25s, −0.32 for 55+.
  - Pringles: +0.44 and −0.43.
- **Settings drown them out.** Settings resolve to place tags ("fine dining
  restaurant", "mid-century modern", "event space"). Their Qloo profile describes
  who visits such venues, with strong values of either sign.
- **No rule chosen.** Four alternative aggregations, all defined in advance, were
  scored offline on both runs: entities x3, entities only, no place tags, and both.
  None was consistently better, and choosing one here would fit noise. The flat
  mean stays as shipped.

## Test 4: held out, the larger HarrisX set, written before the run (2026-10-29)

**The pipeline is frozen** exactly as run 2 used it, so these ads test it blind.

**Labels**, from the HarrisX Super Bowl LX release
([harrisx.com](https://www.harrisx.com/posts/harrisx-super-bowl-lx-ad-ranking-lays-last-harvest-is-americas-favorite-ad)):
- **Gen Z overperformers.** Pringles, NERDS, Bud Light, Hellmann's, NFL
  "Champion", Uber Eats, Frank's RedHot, Kinder Bueno. HarrisX names each as a
  Gen Z top performer outside the overall top 15.
- **Overall leaders, not Gen Z standouts.** The overall top 10 less the
  Blue Square ad:
  - Lay's, Ring, Pepsi "The Choice", Google, Dove, Novartis, Budweiser "American
    Icons", Xfinity "Jurassic Park… Works", NFL "You Are Special";
  - Lay's is #1 with Millennials, Gen X and Boomers, and #4 with Gen Z;
  - Blue Square "Sticky Note" (#5) was run but is left out of the pairs, since an
    anti-hate PSA has no cultural cues to speak of.

**New ads.** Uber Eats, Frank's RedHot, Kinder Bueno, Pepsi "The Choice", Dove,
Novartis, Budweiser, Xfinity, NFL "You Are Special", Blue Square.

**Names given.** From the ad titles and the YouGov celebrity-recall article:
- Matthew McConaughey, Bradley Cooper, Parker Posey;
- Ludacris;
- William Fichtner, Paige DeSorbo;
- Rob Gronkowski, Tony Gonzalez;
- Jeff Goldblum, Sam Neill;
- for Budweiser, Lynyrd Skynyrd's "Free Bird" as the music.

**Prediction.**
- P6. Over all 8 x 9 = 72 (Gen Z overperformer, leader) pairs, using the run 2
  reports for the original ads, more than half rank the Gen Z overperformer as
  more youth-leaning. Chance is 50%; with this much noise, anything under about
  60% is not evidence.

## Test 5: the scores' raw material, cue by cue (YouGov, Super Bowl 2026)

**Source.** YouGov asked 925 US Super Bowl viewers which personalities they
recalled from the ads, by generation and gender
([YouGov](https://yougov.com/en-us/articles/54113-celebrity-recall-who-scored-big-in-super-bowl-2026-ads)).
Recall is not liking, but who notices a celebrity is close to who follows them.

**Contrasts.**
- **Younger** (Gen Z recall above Boomers): Sabrina Carpenter, MrBeast,
  IShowSpeed, Druski, Lady Gaga.
- **Older:** Ted Danson, Jason Alexander.
- **Men:** Tom Brady, Rob Gronkowski, Peyton Manning.
- **Women:** Kendall Jenner, Lady Gaga.

**Prediction.**
- P7. Qloo's own profile (under 25 minus 55+, and female minus male) points the
  same way as YouGov for most of these 12 contrasts. The LLM alone is asked the
  same, for comparison.

### Test 4 results: held out (2026-10-29)

| ad | group | Qloo gap (<25 − 55+) | scored |
|---|---|---|---|
| Uber Eats | genz | −0.42 | 16/26 |
| Frank's RedHot | genz | −0.25 | 12/21 |
| Kinder Bueno | genz | −0.15 | 6/14 |
| Pepsi · The Choice | leader | −0.09 | 13/21 |
| Dove | leader | −0.10 | 11/23 |
| Novartis | leader | −0.10 | 17/26 |
| Budweiser · American Icons | leader | +0.01 | 8/14 |
| Xfinity · Jurassic Park | leader | −0.35 | 10/15 |
| NFL · You Are Special | leader | +0.26 | 14/24 |
| Blue Square (not in the pairs) | psa | −0.05 | 5/13 |

| | Qloo-scored overall | LLM alone (same cues, same audiences) |
|---|---|---|
| **P6** (all 72 pairs) | **FAIL: 24/72 (33%)**, below chance | 59/72 (82%) |
| the 18 pairs among the new ads | 2/18 | n/a |

## Test 5 results: cue by cue

| person | contrast | YouGov | Qloo | LLM alone |
|---|---|---|---|---|
| Sabrina Carpenter | age | younger | ✓ | +0.90 ✓ |
| MrBeast | age | younger | ✓ | +0.90 ✓ |
| IShowSpeed | age | younger | no data | +0.95 ✓ |
| Druski | age | younger | ✓ | +0.80 ✓ |
| Lady Gaga | age | younger | ✓ | +0.30 ✓ |
| Ted Danson | age | older | ✓ | −0.80 ✓ |
| Jason Alexander | age | older | no data | −0.70 ✓ |
| Tom Brady | gender | men | ✓ | −0.60 ✓ |
| Rob Gronkowski | gender | men | ✓ | −0.80 ✓ |
| Peyton Manning | gender | men | no data | −0.60 ✓ |
| Kendall Jenner | gender | women | ✓ | +0.80 ✓ |
| Lady Gaga | gender | women | ✓ | +0.60 ✓ |

**P7 PASS** for the 9 contrasts Qloo has data for (9/9). The 3 without data are
real gaps: the person entities exist in Qloo but carry no audience. The LLM alone
gets 12/12; these are famous people, which is what an LLM knows best.

## Conclusions so far

1. **The data is right; the ad-level score is not.**
   - Cue by cue, Qloo's audience profiles agree with an independent survey every
     time Qloo has a profile.
   - Averaged over every cue into one score per ad, they do not predict which
     generation preferred an ad. On the held-out set the score was below chance,
     while the LLM alone, reading the same cue list, got 82%.
2. **Why, as far as can be seen.**
   - HarrisX measures how much an age group liked an ad: humour, story,
     craft. A mean of cue demographics measures who the ad's ingredients belong
     to.
   - Uber Eats is the clearest case: an older-skewing cast (McConaughey, Bradley
     Cooper) in an ad Gen Z rated highly.
   - Setting and place tags add strong, noisy profiles to the mean, and every
     re-reading of the video changes the cue list (gaps moved by up to 0.55
     between runs).
3. **What can be claimed.**
   - Culture Check reports who each cue in a video reaches, with Qloo data that
     checks out against survey data, and finds same-role replacements.
   - It cannot claim that its overall score predicts how an age group will rate
     an ad. On this evidence, an LLM's cue-by-cue guesses do that better.
   - Test 6, below, replaced the averaged score with a judgement. That is what the
     page shows, and it still cannot claim to predict ratings: it is about 56% on
     these pairs, and Qloo's numbers did not improve it. It is a reasoned reading
     of the evidence, labelled as a judgement.

## Test 6: the judged appeal, written before it was run (2026-10-29)

**What changed.** The video-level verdict is now a judgement, made once per video for
all six age groups (`culturecheck/appeal.py`). The model reads:
- Qloo's per-cue affinities by age, weighted by salience;
- what cues cannot carry (tone, humour, story, format), named on the page with the
  age group each pulls toward.

The per-cue answer (which cues reach which age group) is Qloo's data alone,
unchanged, and is what Test 5 checks.

**Method.**
- The run 2 reports are reused, so the cue lists are the ones Tests 1-4 scored.
- Each ad is judged twice by the same prompt: with Qloo's affinities, and from the cues
  alone (the ablation).
- `python scripts/validate_appeal.py` runs it: 2 LLM calls per ad, not yet run.

**Caveat, stated in advance.** The LLM may know some of these ads or celebrities from
its training data, which flatters both arms equally. The ablation is what isolates
Qloo's contribution.

**Predictions.**
- P8. With Qloo, more than half of the 72 (Gen Z overperformer, leader) pairs rank the
  Gen Z overperformer as more youth-leaning.
- P9. With Qloo, at least as many pairs right as from the cues alone.
- P10. Copy Nothing judged below E-PACE for 45-54s, with Qloo.

### Test 6 results (2026-10-30)

The first draw is the pre-registered result. Two more draws of both arms were added
afterwards, only to measure noise; they were not pre-registered. The chance level is a
one-sided permutation test of the 17 ads' group labels.

| arm | draw 1 (pre-registered) | draw 2 | draw 3 | chance level, draw 1 |
|---|---|---|---|---|
| judged with Qloo | **42/72 (58%)** | 39.5/72 (55%) | 40/72 (56%) | p = 0.30 |
| judged from the cues alone | 44/72 (61%) | 45/72 (62%) | 43/72 (60%) | p = 0.24 |

For comparison, on the same 17 ads and pairs:

| method | pairs right | chance level |
|---|---|---|
| Mean of Qloo's cue scores (Test 4) | 24/72 (33%) | p = 0.88 |
| LLM guess for each cue, averaged (Test 4) | 59/72 (82%) | p = 0.01 |

| prediction | result |
|---|---|
| P8 more than half right, with Qloo | **Nominal pass**, 42/72, but not distinguishable from chance on 17 ads |
| P9 with Qloo at least level with the cues alone | **FAIL**, 42 v 44, and behind in all three draws |
| P10 Copy Nothing below E-PACE for 45-54s, with Qloo | **FAIL** in all three draws (−0.42 v −0.46, −0.34 v −0.60, −0.48 v −0.58). The cues-alone arm got it right in all three |

**Reading it.**
- The judgement is better than the mean of the cue scores (33% to about 56%), but it does
  not beat chance on this sample.
- Qloo's numbers did not help the judgement. If anything they cost a few pairs, in the
  same direction in every draw. The system prompt says measured data outranks the
  model's impressions, so strong profiles on weak cues can steer it: on Ring, "suburban
  residential neighborhood" and "community PSA" drive the whole verdict.
- The same model scores 82% when it guesses cue by cue and 60% when it judges the whole
  video. Only the first is clearly above chance. Why they differ is not known, and either
  may reflect training data, as this test warned; nothing here isolates that.
- The noise is large. An ad's gap moved by a median of 0.17-0.20 across draws, and by up to
  0.74.
- The prompt was deliberately not retuned on these ads: a score reached by tuning on the
  test set would say nothing. With 17 ads, a real difference of a few pairs cannot be
  resolved either way.

**Exploratory, not pre-registered (2026-10-30).** Rescoring the stored Test 4 views on the
same 72 pairs, one draw each. These looked at the test set, so they are leads only.

| scoring | pairs right |
|---|---|
| LLM, all cues | 59/72 (82%) |
| LLM, named entities only | 63.5/72 (88%) |
| Mean of Qloo and LLM per cue | 56/72 (78%) |
| Qloo for named entities, LLM elsewhere | 55/72 (76%) |
| Qloo, recentred within each kind of cue | 30/72 (42%) |
| Qloo, named entities only | 29/72 (40%) |

- No combination beat the LLM alone, and recentring did not rescue Qloo's score.
- Qloo scored 187 of 313 cues. Only 55 cues were named entities (a median of 3 of 17 per
  ad), and only 3 scored cues were music.
- Qloo's age skew depends on the kind of cue: settings average −0.78 and food tags −0.78
  (older), while brands average +0.23 (younger).
- Qloo and the LLM agree on the direction of a cue's age skew only about 45% of the time
  (46% of 48 named entities, 43% of 139 tags). No independent data yet says which is
  right when they differ. The LLM's rating also sees the video's context, which Qloo's
  does not.
- The LLM's cue guesses have one draw only, so the 82% has not been checked for noise.

## Test 7: was the audience actually reached? Written before any ad was collected (2026-10-30)

**Why a new test.** The claim is that Culture Check can tell from what is in an ad who it
reaches. HarrisX measures who liked an ad. The EU's ad transparency rules make Meta
publish who an ad reached, by age, for ordinary commercial ads as well as political ones.

**Data.** For each ad, the Meta Ad Library's "EU ad delivery" table: reach by location, age
and gender. The tables and videos were read in a browser session and are not in this
repository. The measure is the reach-weighted mean age, using bucket midpoints (18-24: 21,
25-34: 29.5, 35-44: 39.5, 45-54: 49.5, 55-64: 59.5, 65+: 70) and pooling all countries.

**Which ads, fixed in advance.** Work through these brands in order, taking whole brands
only, until time runs out:

Vinted, Volvo, Duolingo, Lidl, Red Bull, IKEA, Revolut, Bosch Home, About You, HelloFresh,
Zalando, Booking.com.

For each brand, take the first three ads in the library's own order that are all of:
- one video of 90 seconds or less;
- targeted at 18-65+ and all genders, so any age skew comes from delivery, not the
  advertiser's choice of ages;
- started on or after 2026-09-01, so the ad itself is unlikely to be in an LLM's training
  data (the brands still will be);
- at least 50,000 EU reach.

An ad is not swapped out once seen. If a brand has fewer than three, it keeps what it has.

**Blind.** Predictions are made and stored from the video alone (`scripts/reach.py
--predict`), before reach is read. No cast or music is given.

**Arms.** For each, the prediction is its under-25 score minus its 55+ score.
- `judged`: the page's judged appeal, with Qloo.
- `judged_alone`: the same judge from the cues alone.
- `qloo_mean`: the weighted mean of Qloo's cue scores.
- `llm_cues`: the LLM's guess per cue, weighted the same way.

**Predictions.** Across brands, a brand's general audience can do the work; within a
brand, only the ad differs, so within-brand pairs test the claim most directly.
- P11. `judged` correlates with actual youth of reach across all ads (Spearman, one-sided
  permutation p < 0.05).
- P12. `judged` ranks more than half of the within-brand pairs correctly.
- P13. `judged` is at least level with `judged_alone` on both measures.
- P14. `qloo_mean` is at least level with `llm_cues` on both measures.

**Known limits, in advance.** Delivery is shaped by Meta's algorithm, budget and country
mix, and by who uses Meta at all, so all arms are scored on rank and not on matching shares.
Reach is not liking. Qloo's age profiles ignore location, and these are European ads, some
not in English.

**Change to the sample, made before any ad was collected (2026-10-30).** Cut from 36 ads to
4: the first two eligible ads from each of the first two brands, Vinted and Volvo, searched
in Germany with the library's own order. The other rules stand. Four ads cannot test P11-P14:
this is a small demonstration on real reach data, and the predictions stay unresolved
however it comes out.

**Second change, after checking targeting but before seeing any ad's age mix.** The three
Vinted ads and one Volvo ad that met the date rule were targeted narrowly (women 18-34,
18-44, 25-65+), and broad targeting is the rule that makes the test mean anything. So the
date rule moves from 2026-09-01 to 2026-01-01 and the targeting rule stays. Volvo is limited
to Volvo Car Deutschland, in list order, checking at most eight ads per brand. Ads from
early 2026 are more likely to be known to an LLM than those from autumn.

**Third change, still before seeing any age mix.** None of the 8 Vinted ads or 8 Volvo ads
checked was 18-65+, but each brand repeats its targeting: 8 of 8 Volvo ads are 25-65+ and all
genders, and 6 of 8 Vinted ads are 18-44 and all genders. Two ads of one brand with identical
targeting serve the rule's purpose, because a difference in age mix between them cannot come
from the advertiser's choice of ages. So the demonstration is: the first two ads per brand
with that targeting and 90 seconds or less, compared within the brand only. Brands are not
compared with each other, since their windows differ. That is two pairs, so each arm can
only score 0, 1 or 2.

**Correction, after the age mix of the first four ads was seen.** The collection script took
the first video element on the page, not the one in the ad's dialog, so both Vinted ads were
analysed from the same wrong 21-second film (the Library shows 15 seconds). The Volvo videos
were right: their lengths match the Library and the analysis matches each ad's copy. The
script now reads the dialog's video and checks its length against the Library. The two Vinted
ads are unchanged and were predicted again from the right films. The pipeline never sees reach,
but the analyst had already seen those two ads' age mix when rerunning them.

One thing from the mistake is still a valid measurement: the same file analysed twice gave
different predictions, with `qloo_mean` +1.28 and +0.38 and `judged` +1.35 and +1.02.

### Test 7 demonstration results (2026-10-30)

Germany only, same brand and same targeting within each pair. A prediction is the under-25
score minus the 55+ score, so higher means younger. The Nike pilot's video also matches its
ad's copy.

| pair | ad | length | reach | mean age of reach | `judged` | `judged_alone` | `qloo_mean` | `llm_cues` |
|---|---|---|---|---|---|---|---|---|
| Vinted, 18-44 | 1231500332376639 | 15 s | 4.5M | 30.98 | +0.32 | +0.50 | +0.24 | −0.14 |
| | 1321958429767586 | 15 s | 3.8M | 31.05 | +0.92 | +1.20 | +0.07 | +0.63 |
| Volvo, 25-65+ | 3226341090863533 | 15 s | 7.8M | 40.94 | +0.22 | −0.15 | +0.36 | −0.54 |
| | 1499603775052984 | 6 s | 13.7M | 42.17 | −0.35 | −1.18 | −0.03 | −0.61 |

- Volvo: all four arms picked the younger-reaching ad.
- Vinted: the two ads differ by 0.07 years, which is effectively a tie, so no arm's result
  there means anything (`qloo_mean` was right, the other three wrong).
- P11-P14 stay unresolved. Two pairs, one of them a tie, is far too few.
- Caveats: three of the four ads have several versions, and only the first was analysed
  while reach covers them all. The Volvo pair also differs in length and model.

**What it suggests.** With targeting held equal, the age mix barely moved: by 0.07 and 1.23
years, against about 10 years between the two brands' windows. On these ads, who an ad reached
looks set mostly by who the advertiser targeted, so delivery data may hold little signal about
creative. Two pairs only suggest this. It would need testing on more ads before relying on it.

**Pilot, outside the sample (2026-10-30).** One Nike ad, Library ID 28219399641026721: a
French creator's family video in a Nike Factory Store, 76 s, 18-65+, all genders, 6.6M
reach, August-September 2026 (too early for the sample's date rule). Predicted blind from
the video Meta served, then checked.

| | under 25 / 18-24 | 25-29 | 30-34 | 25-34 | 35-44 | 45-54 | 55+ |
|---|---|---|---|---|---|---|---|
| Judged appeal, with Qloo | +0.06 | +0.11 | +0.55 | | **+0.70** | −0.12 | −0.18 |
| Actual share of reach | 17.9% | | | **36.0%** | 19.8% | 13.1% | 13.3% |

The prediction's peak was 35-44 and the actual peak was 25-34. One ad cannot be scored, and
25-34 may simply be the largest age group on Meta, so this only shows the method runs end to
end. Rankings across many ads are what Test 7 scores.

## Test 6 addendum: live check of the app

**Live check of the app, same day.** Uploads went end to end with real models on two ads
(58 s and 70 s), with all refusals, chat, frames and video range working. Reading the real
output found faults a stub could not show:
- The advertised brand was being offered as a swap (Ring to Yelp, Jaguar to Aprilia). A
  prompt rule did not stop this, so `swaps.advertised` now excludes it in code.
- The brief credited the age-only judgement to a gender and a city, and to Qloo. The prompt
  now forbids this, which worked on the Ring sample but not the Jaguar one ("Off for men
  45-54").
- Swaps for kinds of thing (tags) are often weak: "Talk-show" for a midcentury home,
  "Barbershop" for a porch conversation. Entity swaps are the ones to trust.
