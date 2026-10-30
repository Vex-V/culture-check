# vidra, vendored

This folder is a copy of **vidra**, the video RAG library Culture Check is
built on (a video in; answers to questions about each shot, a transcript and a
searchable index out). It is maintained in its own repository; this copy is
here so Culture Check installs and runs from this repository alone.

- Copied from vidra at commit `c8aa3c1` (2026-10-23), plus one fix made
  upstream at the same time: the Whisper backend asks CTranslate2, not torch,
  whether there is a GPU, so transcription needs no torch.
- Culture Check uses: the components one by one (`media`, `audio`,
  `boundaries`, `video`, `cut`, `describe`, `embed`) with a `scene` grid,
  `describe.add_question` for the `culture` question, `search` over a
  `Folder`, and `Models` with `OpenAI` and `OpenAIEmbedder`.
- Only the core install and faster-whisper are needed: no torch, no
  detectors, no speaker model.
- vidra is MIT-licensed; its notice is [LICENSE](LICENSE), beside this file,
  and goes wherever this copy does.

To update it, copy the `vidra/` package from the vidra repository over this
folder and keep this file and `LICENSE`.
