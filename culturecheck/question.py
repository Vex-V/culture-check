"""The question vidra asks of every shot, registered with the library at
start-up.

    culture     what in this shot signals taste: the setting and its era,
                named places, brands, what people wear, eat and do, works and
                people referenced, the visual style, the words on screen.

People are described by look and age range, never identified; a public figure
counts only when named on screen.
"""

from __future__ import annotations

from typing import Any

NAME = "culture"

QUESTION: dict[str, Any] = {
    "instruction": (
        "These {n} frames are one shot of a video (an advert or a creator's "
        "video) and span {span}. List what in them signals taste and culture, "
        "the things a brand strategist would notice. Be specific and concrete: "
        "'a 1950s chrome roadside diner', not 'a restaurant'. Name a brand, "
        "place, work or person only when it can be read or recognised from the "
        "frames (a logo, a sign, a caption, a famous landmark); never guess a "
        "name, and never identify a person from their face. Leave a list empty "
        "when the shot has nothing for it."),
    "fields": {
        "setting": {"type": "text",
                    "about": "the kind of place, as specifically as the picture "
                             "allows, with its era or price point when it shows"},
        "places": {"type": "list", "about": "named, recognisable places: a city, "
                   "landmark, venue or chain",
                   "of": {"name": "the place's name",
                          "evidence": "how it is known: a sign, a landmark, a caption"}},
        "brands": {"type": "list", "about": "each brand visible or shown",
                   "of": {"name": "the brand's name, as written",
                          "how": "logo, product, packaging, sign, caption or vehicle",
                          "detail": "what carries it: 'the cap', 'the can on the table'"}},
        "wardrobe": {"type": "list", "about": "what people wear that says something "
                     "about taste",
                     "of": {"item": "the garment or accessory",
                            "style": "the style or subculture, as a stylist would "
                                     "name it: streetwear, preppy, workwear, "
                                     "athleisure, 1970s disco, ...",
                            "brand": "the brand if a logo is legible, else 'none'"}},
        "food_drink": {"type": "list", "about": "food and drink shown",
                       "of": {"item": "the dish or drink",
                              "cuisine": "the cuisine or category",
                              "brand": "the brand if legible, else 'none'"}},
        "activities": {"type": "list", "about": "what people do that signals a "
                       "lifestyle or scene: skateboarding, golf, gaming, a house "
                       "party, a road trip, ..."},
        "references": {"type": "list", "about": "works and public figures shown or "
                       "referenced: a poster, a screen, a book cover, a caption",
                       "of": {"title": "the name, as shown",
                              "kind": "one of: film, tv_show, book, artist, song, "
                                      "person, video_game, podcast, sports_team, "
                                      "event, other",
                              "evidence": "where it appears"}},
        "music_seen": {"type": "list", "about": "music visible in the picture: a "
                       "band or instrument played, a song or artist credit on "
                       "screen, a record sleeve"},
        "cast": {"type": "text", "about": "who appears, by approximate age range "
                 "and look (never by identity); 'nobody' when nobody does"},
        "aesthetic": {"type": "text",
                      "about": "the visual style and the era or scene it evokes, "
                               "as a creative director would name it"},
        "on_screen_text": {"type": "list", "about": "taglines, captions and other "
                           "words on screen, verbatim"},
    },
    "summary": "brief",
}


def register() -> None:
    """Add (or refresh) the question. Idempotent: the same text hashes the same,
    so nothing already answered goes stale."""
    from vidra.video_rag import describe

    describe.add_question(NAME, QUESTION["instruction"], fields=QUESTION["fields"],
                          summary=QUESTION.get("summary"))
