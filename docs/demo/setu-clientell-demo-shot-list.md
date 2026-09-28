# SETU — Clientell two-minute recording plan

## Editorial rule

Treat every connected answer as **recorded evidence**. Do not submit a live
query during recording. Keep a small persistent label, “Recorded connected
evidence,” over the e-Shram and Hindi PMSBY shots. The final cut should run from
1:55 to 2:00 and must not exceed 2:00; this plan totals 2:00.

## Compact architecture frame

Use the recording-ready 1920×1080 asset:

`docs/demo/assets/setu-architecture.svg`

“Hybrid retrieval” means BGE-M3 query embedding, PostgreSQL/pgvector dense
search, PostgreSQL full-text search, and reciprocal-rank fusion. Keep those
details in narration or subtitles rather than adding another diagram.

## Timed shot list

| Time | Duration | Spoken narration | Exact screen or asset | Cursor or edit sequence | On-screen caption | Evidence | Transition |
|---|---:|---|---|---|---|---|---|
| 0:00–0:07 | 7 s | “Government-service information is scattered across portals.” | `docs/demo/assets/setu-title-frame.png` | Start on a still crop of the SETU header and hero. Add a slow 3% push-in; no cursor. | `SETU · Official evidence, clearer answers` | Exact copy of the saved deterministic UI screenshot; see manifest EV-01. | Cross-dissolve into the workspace crop. |
| 0:07–0:15 | 8 s | “SETU is a multilingual public-information assistant that answers questions from official evidence and shows where each answer came from.” | Same landing image, panned toward the workspace call to action, then a one-second title card | Move the cursor once toward “Ask”; do not click or launch a query. | `Multilingual public-information assistant` | Product positioning required by the brief and supported by README/workspace behavior. | Match-cut the title text to the first architecture node. |
| 0:15–0:35 | 20 s | “A question enters FastAPI and LangGraph. SETU combines pgvector dense search with PostgreSQL full-text search, reranks selected evidence, calls the chat model, then validates citations and numbers before returning a bounded response.” | `docs/demo/assets/setu-architecture.svg` | Move left to right across each node in narration order. Briefly highlight “Hybrid retrieval,” “RRF + rerank,” and “Grounding validation.” | Already embedded in the asset | Implemented modules listed in manifest EV-02. | Zoom through the final “Grounded response” node into the recorded answer. |
| 0:35–0:48 | 13 s | “This is recorded evidence from a connected local test, not a live query. I asked, ‘How do I register for e-Shram and what do I need?’ SETU answered that I need an Aadhaar number and Aadhaar-linked mobile number.” | `docs/demo/assets/e-shram-recorded-result.png` | Fit the 1440×950 screenshot inside the 1920×1080 canvas without stretching or cutting evidence. Hold on the full answer; move the cursor from the exact question to the answer sentence. Do not click the composer. | `RECORDED CONNECTED EVIDENCE · English` | Saved HTTP 200 response; see manifest EV-03. | Punch in toward citation badge `1`. |
| 0:48–1:00 | 12 s | “The citation maps to the official e-Shram FAQ passage, while separate controls lead to official registration and help pages.” | `docs/demo/assets/e-shram-evidence-card.svg` | Highlight citation ID, the two requirements, then source, application, and help destinations. | Already embedded in the asset | Saved response evidence; see manifest EV-04. | Hard cut on the words “failure path.” |
| 1:00–1:15 | 15 s | “During development, Groq returned a structured-output `tool_use_failed` error. I traced it to the request format and forced-tool path created by Instructor.” | `docs/demo/assets/groq-structured-output-fix.svg` | Start framed on the left “Before” panel. Box `Mode.TOOLS`, then the sanitized error category. No terminal is visible. | Already embedded in the asset | Parent of commit `9384628` and sanitized regression evidence; see manifest EV-07. | Pan horizontally across the correction arrow. |
| 1:15–1:30 | 15 s | “I removed that inappropriate Groq route and used native strict JSON-schema output. Regression tests now require requests without tools or tool choice, while grounding checks reject unknown citations and unsupported numbers.” | Same `groq-structured-output-fix.svg` | Settle on the right “After” panel, then reveal the bottom regression-protection strip. | Already embedded in the asset | Commit `9384628`, current request-shape tests, and downstream grounding controls; see manifest EV-07. | Dissolve to the Hindi recorded-result frame. |
| 1:30–1:40 | 10 s | “The interface also produced a recorded Hindi PMSBY answer from an official English passage.” | Begin on `docs/demo/assets/pmsby-hindi-recorded-result.png`; crossfade at 1:35 to `docs/demo/assets/pmsby-evidence-card.svg` | Fit the 1440×950 screenshot without stretching or cutting evidence. Trace query → answer → citation; after the crossfade, point from the Hindi answer to the English source passage. | `RECORDED CONNECTED EVIDENCE · Hindi over English evidence` | Saved HTTP 200 response and source passage; see manifest EV-05 and EV-06. | Slide the evidence card left to reveal evaluation. |
| 1:40–1:50 | 10 s | “Sixty of sixty small deterministic fixtures passed across English, Hindi, and Bengali, including abstention and numerical checks. These are regression results, not universal accuracy.” | `docs/demo/assets/deterministic-evaluation-card.svg` | Highlight `60 / 60`, the three language counts, then leave the interpretation boundary visible. | Already embedded in the asset | Frozen report version `4C-2.1`; see manifest EV-08. | Fade into the repository README. |
| 1:50–2:00 | 10 s | “Local inference latency is still too high, so the performance gate remains open. The main engineering problem wasn’t making the model answer. It was knowing when I could trust that answer and preventing unsupported output from reaching the user.” | Repository README title and local `docs/demo/` files in the file tree; finish on the SETU mark | No scrolling. Add the closing line as subtitles, then fade to the SETU mark and repository link supplied during editing. | `Quality gate: OPEN · latency unresolved` | Current checkpoint: connected functionality passed, but warm requests remain several minutes. | Fade to black at exactly 2:00. |

## Asset inventory

### Available and verified

- Repository-local title, connected e-Shram, and connected Hindi PMSBY PNGs.
- Recording-ready architecture, e-Shram evidence, PMSBY evidence, Groq
  failure/fix, and deterministic-evaluation SVGs at 1920×1080.
- Evidence manifest with provenance, privacy decisions, claim qualifications,
  and official-link checks.
- README and checkpoint text for the closing limitation.

### Manual capture and editing still required

1. Open the repository-local assets full-screen and assemble them on the timed
   sequence below; no code or terminal capture is required.
2. Record the clean README/`docs/demo/` closing frame.
3. Add narration and subtitles, verify the Hindi glyphs, and export an MP4 no
   longer than 120 seconds.
4. Upload the final MP4 to a recruiter-accessible location and test access in a
   signed-out browser. Do not expose a private Cloud Run endpoint.

No finished screen recording, narration track, subtitles, MP4, or public video
link currently exists. Do not invent or imply that these assets are complete.

## Recording safety and quality checklist

### Literal recording sequence

1. Close mail, chat, password managers, cloud consoles, terminals, and every
   unrelated browser tab. Disable notifications.
2. Set the editor or browser to 100% zoom at 1920×1080. Open only EV-01 through
   EV-09 from `setu-clientell-demo-evidence-manifest.md`. Center the two
   1440×950 recorded-result PNGs on the canvas without stretching them.
3. Place the cursor outside the visible content. Start recording two seconds
   before EV-01, then pause briefly before the first sentence.
4. Follow the table row by row. Use only the specified single pan, highlight,
   crossfade, or slow push-in; avoid scrolling and extra animation.
5. Pause for half a beat at 0:35, 1:00, 1:30, and 1:50 so each story section
   lands cleanly. Remove those gaps first if the rough cut exceeds 2:00.
6. Keep subtitles to two lines, align them away from evidence text, and verify
   `e-Shram`, `pgvector`, `LangGraph`, `tool_use_failed`, `PMSBY`, and the Hindi
   sentence manually.
7. End on the repository frame with `Quality gate: OPEN · latency unresolved`
   visible. Fade to black by 2:00.
8. Watch the exported MP4 once with sound and once muted before uploading.

- [ ] Record and export at 1920×1080.
- [ ] Use browser/editor zoom that keeps every caption and code line readable.
- [ ] Hide API keys, authorization headers, connection strings, project IDs,
      private service URLs, private addresses, personal data, and notifications.
- [ ] Close unrelated windows, terminals, browser tabs, and messaging clients.
- [ ] Do not show `.env`, shell history, browser history, cloud consoles, or
      clipboard managers.
- [ ] Do not show long loading periods or submit a fresh inference request.
- [ ] Keep “Recorded connected evidence” visible on recorded-result shots.
- [ ] Add accurate subtitles and manually check technical names and Hindi text.
- [ ] Keep music absent or quiet enough that speech remains clear.
- [ ] Verify the public official source, application, and help links immediately
      before recording; omit any destination that no longer resolves.
- [ ] Keep the final cut between 1:55 and 2:00; never exceed 2:00.
- [ ] Export an MP4 and prepare a recruiter-accessible link.
- [ ] Test the final link while signed out and on a second device.
- [ ] Never expose a private Cloud Run endpoint merely for the demo.
- [ ] Keep the closing latency limitation on screen long enough to read.

## Evidence handling notes

- Connected answer screenshots and JSON are recorded local evidence with real
  retrieval and deterministic external generation boundaries.
- The Hindi answer is supported by an English official passage; the answer
  language and evidence language should not be conflated.
- The offline 60/60 result is deterministic fixture replay. It is not a live
  accuracy benchmark.
- Citation validation proves retrieved-ID membership and de-duplication, not
  semantic entailment.
- Model-reported confidence is uncalibrated and is intentionally absent from
  narration.
- Local inference latency remains an open gate; editing out waiting time makes
  the interview demo watchable but does not resolve system performance.
