# Culture Check

Culture Check shows which age groups a video's cultural cues reach.

Upload an ad and choose a target audience. Culture Check finds the brands, places,
clothes and settings in each shot, looks up who each one reaches in
[Qloo's taste graph](https://www.qloo.com/), and suggests replacements for the cues
that miss.

## What it shows

- **Who each cue reaches:** Qloo's audience data for each cue, by age and gender.
- **Who each moment reaches:** the same data shot by shot.
- **Appeal of the whole video:** a score from −1 to 1 for each of six age groups,
  judged by a model from Qloo's data and from what cues can't capture, such as tone
  and humour.
- **Replacements:** alternatives for cues that miss, scored for the same audience.
- **A written brief:** what works, what misses and what to change.
- **An analyst:** answers follow-up questions by querying Qloo.
- **Real-world results:** judged appeal next to the reach by age that Meta publishes
  for ads shown in the EU.

## How it works

1. **Read the video.** [vidra](vidra/VENDORED.md) cuts the video into shots of 2–8
   seconds, describes each shot and transcribes the sound.
2. **Find the cues.** A model merges the shots into a list of cues.
3. **Match the cues.** Named things go to Qloo's `/search`. Kinds of thing, such as
   "diner", go to `/v2/tags`.
4. **Get the audiences.** One `urn:demographics` call returns each cue's affinity for
   six age groups and two genders. With a city, `/v2/insights` adds its local following.
5. **Judge the video.** A model scores the whole video for all six age groups, giving
   more weight to talent, music and brands than to background settings.
6. **Find replacements.** Qloo proposes alternatives and scores them. A model keeps
   those that fit the shot.
7. **Answer questions.** The analyst has five tools:

   | Tool | What it does |
   |---|---|
   | `check_fit` | Scores a named thing or style for the audience |
   | `explore` | Lists what the audience likes in a category |
   | `what_if` | Re-scores every cue for another audience |
   | `find_moment` | Searches the video's shots |
   | `cue_detail` | Returns everything held about one cue |

## Accuracy

Predictions were written before each test ran. Full results are in
[eval/VALIDATION.md](eval/VALIDATION.md).

| Test | Result |
|---|---|
| Do Qloo's cue audiences match a YouGov survey of celebrities? | 9 of 9 where Qloo has data, 9 of 12 overall |
| Can the whole-video score tell which generation preferred an ad? | About 56% of 72 ad pairs, not distinguishable from chance on 17 ads |
| Does the whole-video score match real Meta reach? | One usable pair, which it got right. Too few to count |

- Use the cue-level data as measurement. Treat the whole-video score as a judgement.
- An LLM without Qloo scored as well or better on these tests.
- In the Meta ads tested, reach changed little between ads with the same targeting.

## Limits

- Songs are not recognised. Type the soundtrack into the upload form.
- People are not identified from their faces. Type their names into the upload form.
- Qloo has no audience data for about 40% of cues.
- Style and setting replacements are weaker than brand and artist replacements.
- Results vary between runs, because each run reads the cues afresh.

## Run it

Requires Python 3.11 or later, an OpenAI key and a Qloo key.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e .
cp .env.example .env             # add your keys
culturecheck                     # http://127.0.0.1:8000
```

To run one video from the command line:

```bash
python scripts/run.py VIDEO --age 25_to_29 --gender female --location Austin
```

A minute of video takes about a minute on a CPU.

## Data

Qloo's responses are stored privately and are not in this repository. Uploaded frames
and transcripts are sent to OpenAI.

## Licence

MIT, for this code and for the vendored copy of vidra ([vidra/LICENSE](vidra/LICENSE)).
