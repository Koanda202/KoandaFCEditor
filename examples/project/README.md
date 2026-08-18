# Example project layout

This folder shows the zero-config layout `koanda-editor` expects — only
`story.txt` is included here since sample video/audio isn't checked into
the repo. To try it yourself, add:

```
examples/project/
  clips/
    session1.mp4        <- your raw ROG Ally recordings, any names
    session2.mp4
  vo/
    01_opening.mp3       <- voice lines, named so sorted order = story order
    02_boss_fight.mp3
  story.txt              <- already here
```

Then run:

```bash
koanda-editor examples/project
```

- `story.txt` lines become scenes, in order — that's it, no editing needed.
- `vo/` files are matched to scenes 1:1 in sorted filename order (so name
  them `01_...`, `02_...` to control the pairing). Extra story lines beyond
  the number of VO files just get no narration.
- `clips/` is scanned automatically for the loudest moment to fill each
  scene.

Output lands at `examples/project/output/final_video.mp4`.
