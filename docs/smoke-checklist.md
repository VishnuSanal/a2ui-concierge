# Live Demo Smoke Checklist

What the engineer (or you, in person) does before any live demo to make sure the system is healthy.

## Prerequisites
- `ANTHROPIC_API_KEY` is exported in the shell that will run the backend.
- An Android emulator is booted (Pixel-class image, API 34+) OR a physical phone is connected via USB with USB-debugging enabled.
- The phone or emulator can reach the backend host (emulator: `10.0.2.2:8000` is the host loopback; physical phone: use Cloudflare Tunnel or `adb reverse tcp:8000 tcp:8000`).

## Steps

1. **Start the backend.**
   ```bash
   cd backend && uv run uvicorn concierge.app:app --host 0.0.0.0 --port 8000
   ```
   Confirm `GET /health` returns `{"status":"ok"}`.

2. **(Physical phone only) Set up reverse tunnel.**
   ```bash
   adb reverse tcp:8000 tcp:8000
   ```
   Then change `BACKEND_BASE_URL` in `app/app/build.gradle.kts` to `"http://localhost:8000"` and rebuild.

3. **Install the Android app.**
   ```bash
   cd app && ./gradlew :app:installDebug
   adb shell am start -n com.diegoz.a2uiconcierge/.MainActivity
   ```

4. **Walk the six storyboard beats.**
   - Beat 1: type "Need a gift for my sister — minimalist, under $150" and send.
   - Beat 2: agent shows clarifying chips. Tap "Jewelry".
   - Beat 3: agent shows three product cards. Tap the Bar Pendant ($124).
   - Beat 4: agent shows variants (finish, length). Pick Silver / 16". Tap Continue.
   - Beat 5: agent shows form. Toggle gift wrap on, type a note, pick an address. Tap Place order.
   - Beat 6: agent shows the confirmation card. A subtle haptic should fire.

5. **Capture artifacts.**
   ```bash
   mkdir -p docs/screenshots
   adb shell screencap -p /sdcard/s.png && adb pull /sdcard/s.png docs/screenshots/beat-3.png
   # repeat after each beat
   adb shell screenrecord /sdcard/demo.mp4 --time-limit 30
   adb pull /sdcard/demo.mp4 docs/screenshots/demo.mp4
   ```

## Common failures and fixes

- **Cold-start agent first byte > 5 seconds:** prompt cache hasn't warmed. Send a throwaway message first, then start the recording on the second turn.
- **WebView shows blank rectangle:** confirm the host bundle was rebuilt and copied (`cd host-bundle && npm run build:android`) and the app was reinstalled afterward.
- **`Could not find dev.jeziellago:compose-markdown`:** the dependency lives at `com.github.jeziellago:compose-markdown` on JitPack — `settings.gradle.kts` must list `maven { url = uri("https://jitpack.io") }`.
- **Cleartext error on physical phone:** `android:usesCleartextTraffic="true"` is set in the manifest for HTTP. If using a real tunnel with HTTPS, this can be tightened.

## Done when

- All six beats render correctly without retry.
- The confirmation card fires a haptic.
- `docs/screenshots/demo.mp4` is a clean 30-second recording.
