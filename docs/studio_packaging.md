# Studio Packaging

The target local app flow is:

```bash
uv tool install "hephaestus[studio]"
heph studio
```

From source:

```bash
uv sync --extra studio
cd apps/studio
pnpm install
pnpm build
cd ../..
uv build
```

## Static Assets

`pnpm build` exports the frontend to:

```text
apps/studio/out/
```

The wheel build force-includes that export under:

```text
hephaestus/studio/static/
```

At runtime, Studio static discovery checks packaged assets first, then the
source checkout export. If assets are missing, `heph studio doctor` reports
actionable guidance.

## Validation

Package validation should include:

```bash
uv build
```

Then install the built wheel into a temporary isolated environment and run:

```bash
heph --help
heph studio doctor
heph studio --no-open
```

For the launch smoke, bind to localhost and stop the server after verifying
health and static frontend load. Do not leave servers running.

## Platform Notes

- Windows paths are supported and validated in tests.
- Linux and macOS use the same localhost browser-served app model.
- Electron/Tauri packaging is intentionally deferred.
- Studio binds to `127.0.0.1` by default.
