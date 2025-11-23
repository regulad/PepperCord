# TODO

The following checklist items represent features I'd like to add to PepperCord.

Their inclusion on this list is not a guarantee that they will eventually be implemented.

- [ ] Proper handling of a SIGINT (e.g., graceful shutdown) (d.py handles this with the standard startup wrapper but we rolled our own to manage the database lifecycle)
- [ ] Voice recording/transcription and playback/clipping (essentially adopting the functionality of the defunct `regulad/BigBrother` while also adding transcription functionality) (library in use for the `CustomVoiceClient` enables sinking audio; just need to plumb)
- [ ] Multi-channel audio over RTSP of voice chat for given guild (useful for doing MM productions from a discord channel, great for twitch streaming/yt recording)
- [ ] RSS feed parsing & iCal feed parsing; mentioning in channel when new content on feed is detected (goal was to use this for sports games)
- [ ] TTS using a local model
- [ ] Improved `santa_hat`
- [ ] FNAF3 (all assets are in the source tree, but are entirely unused)
